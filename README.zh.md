# Paper Fetcher

中文 | [English](README.md)

多源学术论文搜索与 PDF 下载工具，支持自然语言交互（Claude Code）。

## 功能

- **多源搜索** — 同时查询 Semantic Scholar API、arXiv 和 Google Scholar
- **智能去重** — 按 DOI + 标题 + 作者合并，保留信息最全的版本
- **自动下载 PDF** — arXiv 直连 → Sci-Hub 多域名回退 → 直接 URL，含指数退避重试
- **主题管理** — LLM 引导的合并策略，相同技术 + 相同应用领域自动归组
- **中英双语** — 完全支持中文搜索和自然语言查询
- **零配置启动** — 首次运行自动创建虚拟环境并安装依赖

## 快速开始

### 前置条件

- Python 3.10+
- [Claude Code](https://claude.ai/code)

### 安装 skill

```bash
claude skill add paper-fetcher <仓库地址>
```

### 或独立运行

```bash
git clone <仓库地址>
cd paper-fetcher

# 安装依赖
pip install -e .

# 查看帮助
python3 skill.py help
```

## 使用示例

### 自然语言（在 Claude Code 中）

```
搜索机器学习论文
下载深度学习的论文
列出已保存的主题
搜索因果推断相关的论文
sci-hub 下载 transformer 论文
```

### 命令行

```bash
# 搜索
papers search --topic "transformer attention" --max 30

# 搜索并合并到已有主题
papers search --topic "医学影像分割" --merge-into medical-image-segmentation

# 强制新建主题（跳过自动合并）
papers search --topic "reinforcement learning" --new-topic

# 下载所有待下载论文
papers download --topic federated-learning --all

# 列出已保存的主题
papers list
```

### Skill 入口

```bash
# 也支持自然语言
python3 skill.py 搜索联邦学习论文
python3 skill.py 下载深度学习
python3 skill.py list
python3 skill.py help
```

## 架构

```
skill.py          ← NLP 意图解析（搜索/下载/列表），自动引导
cli/main.py       ← argparse CLI 入口
core/
├── searcher.py   ← 多源编排、去重、Crossref DOI 补全
├── merger.py     ← 模糊主题匹配（未指定 --merge-into 时使用）
├── downloader.py ← arXiv 直连 → Sci-Hub BS4 提取 → 直接 URL 回退
├── storage.py    ← results.md + papers.json 持久化，.index.json 索引
├── models.py     ← Paper & TopicInfo 数据类
├── config.py     ← YAML 配置，含深度合并默认值
└── sources/
    ├── base.py      ← 抽象基类，含限速器和重试
    ├── arxiv.py     ← arXiv API 客户端
    ├── semantic.py  ← Semantic Scholar API 客户端
    └── scholar.py   ← Google Scholar（通过 scholarly）
```

### 主题合并逻辑

使用 **LLM 语义合并**（非关键词重叠）判断新搜索是否归入已有主题目录。规则：

> **相同技术 + 相同应用领域** = 合并。
> 不同技术或不同领域/粒度 = 新建主题。

详细决策表见 `SKILL.md`。

## 数据存储

搜索结果保存在 `./papers/<主题目录>/` 下：

```
papers/
├── .index.json              ← 主题索引
├── federated-learning/
│   ├── results.md           ← 搜索结果表格
│   └── papers.json          ← 完整元数据（摘要、URL、DOI）
├── 医学影像-cnn/
│   ├── results.md
│   ├── papers.json
│   └── 2024-03-01 U-Net 医学分割.pdf
└── ...
```

## 配置

复制 `config.example.yaml` 为 `config.yaml` 并自定义：

```yaml
sources:
  scholar:
    enabled: true
    delay_min: 10
    delay_max: 20
  semantic:
    api_key: YOUR_SEMANTIC_SCHOLAR_KEY  # 可选，免费申请
download:
  scihub_domains:
    - https://sci-hub.se
    - https://sci-hub.st
storage:
  base_dir: ./papers
```

## 开发

```bash
# 设置
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 运行测试
python3 -m pytest tests/ -v
```

## 许可

MIT
