---
name: paper-fetcher
description: Search academic papers across arXiv and Semantic Scholar, save results to markdown files, and download papers from Sci-Hub. Organizes papers by topic with automatic merge detection.
entry:
  script: skill.py
  interpreter: python3
---

# Paper Fetcher

Search academic papers and download from Sci-Hub.

## Usage Examples

- "search papers on federated learning"
- "download papers from my federated learning results"
- "show my saved topics"
- "find papers about causal inference"
- "sci-hub download deep learning papers"
- "搜索机器学习的论文"
- "下载深度学习相关的论文"
- "列出已保存的主题"

## Triggers

- search paper / search papers
- find paper / find papers
- download paper / download papers
- sci-hub / scihub
- academic search / arxiv / paper search
- 搜索论文 / 下载论文 / 论文搜索 / 论文下载

## Topic Management (LLM-guided merging)

**Before invoking search**, read existing topics from
`$PAPER_FETCHER_CWD/papers/.index.json` (the actual path where papers are
saved) and decide whether to merge. Use semantic understanding — NOT the
rule-based algorithm in `core/merger.py` (which only checks keyword overlap).

### Decision rule

合并条件：**技术栈相同 AND 应用领域相同**，两个维度同时匹配才合并。

**技术栈**（模型/方法/技术路线）：
- 相同：CNN/ResNet/卷积神经网络, Transformer/Attention/ViT, LLM/GPT/大语言模型
- 不同：CNN vs Transformer, CNN vs LLM

**应用领域**（问题场景）：
- 相同：医学影像分割+医学影像分类, 情感分析+文本分类
- 不同（粒度不匹配）：医学影像 vs 医学（泛指）

### 快速决策

| 已有 topic | 新查询 | 合并？ | 理由 |
|---|---|---|---|
| 卷积神经网络医学影像 | cnn 医学影像综述 | 合并 | CNN+医学影像，技术领域均相同 |
| 医学影像分割 | unet 医学影像分割 | 合并 | 技术不同但领域同为医学影像分割 |
| transformer 医学影像 | llm 医学应用 | 不合并 | transformer vs llm 技术不同，领域粒度也不同 |
| 自然语言处理 | transformer 情感分析 | 不合并 | NLP 应用 vs 具体 transformer 技术，粒度不匹配 |
| federated learning | 联邦学习医疗应用 | 合并 | 技术相同（联邦学习），领域为医疗 |

### Invocation

**Prefer natural language** via the Skill tool — it handles CWD, paths,
and flags automatically. Example:

> "search papers on federated learning, merge into existing topic"

Only use CLI-style Bash commands (below) when you need explicit control
over `--merge-into` or `--new-topic`. When you do, set `PAPER_FETCHER_CWD`
to the primary working directory so papers save to the correct location:

- **Merge explicitly**: `--merge-into <slug>` when you've identified a match
  ```
  PAPER_FETCHER_CWD=<primary working directory> python3 skill.py search --topic "..." --merge-into existing-slug
  ```
- **New topic**: `--new-topic` when truly new (overrides auto-detect)
  ```
  PAPER_FETCHER_CWD=<primary working directory> python3 skill.py search --topic "..." --new-topic
  ```
- **Auto (rule fallback)**: omit both flags — `core/merger.py` handles it

Papers are saved relative to `PAPER_FETCHER_CWD` / `storage.base_dir`.

## Behavior

1. Parses natural language input to detect intent (search / download / list)
2. Dispatches to CLI subcommands via `python3 skill.py` → `cli.main`
3. Auto-bootstraps venv and dependencies on first run (see Environment below)
4. Search: queries multiple sources (semantic, arxiv), deduplicates,
   saves results as markdown + JSON. Before searching, decide merge (see
   Topic Management above).
5. Download: reads saved results, fetches PDFs from Sci-Hub
6. List: shows all saved topics with paper counts

## Environment (first run)

On **first invocation**, `skill.py` auto-bootstraps inside the project
directory:

1. Creates a project-local Python venv (`.venv/`) — re-execs into it
2. Installs required dependencies via pip (requests, pyyaml, rapidfuzz, etc.)
3. Auto-creates `config.yaml` from `config.example.yaml` if neither exists

The first run may take 30-60s depending on download speed. Subsequent
invocations skip setup entirely.

### Manual setup (fallback)

If auto-bootstrapping fails or you prefer to install ahead of time:

```bash
cd /Users/matthewtan/project/python/ccbTest
python3 -m venv .venv
.venv/bin/pip install requests pyyaml rapidfuzz beautifulsoup4 semanticscholar arxiv questionary rich
cp config.example.yaml config.yaml   # if config.yaml doesn't exist
```

### Pip mirror for restricted regions

Set `pip_mirror` in `config.yaml` to use a local PyPI mirror
(e.g. `https://pypi.tuna.tsinghua.edu.cn/simple` for mainland China).
