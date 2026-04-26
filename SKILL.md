---
name: paper-fetcher
description: Search academic papers across Google Scholar, arXiv, and Semantic Scholar, save results to markdown files, and download papers from Sci-Hub. Organizes papers by topic with automatic merge detection.
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
- academic search / google scholar / arxiv / paper search
- 搜索论文 / 下载论文 / 论文搜索 / 论文下载

## Topic Management (LLM-guided merging)

**Before invoking search**, check existing topics and decide whether
to merge. Read `papers/.index.json` for current topics. Use semantic
understanding — NOT the rule-based algorithm in `core/merger.py`
(which only checks keyword overlap and is too simplistic).

### How to decide

合并原则：**相同技术 + 相同应用领域**，两个维度同时匹配才合并。

1. **Read existing topics**: check `papers/.index.json` for the topic list

2. **判断技术栈**（使用的模型/方法/技术路线）是否相同：
   - CNN / ResNet / 卷积神经网络 → 相同技术栈
   - Transformer / Attention / ViT → 相同技术栈
   - LLM / GPT / 大语言模型 → 相同技术栈
   - CNN vs Transformer → **不同技术栈，不合并**
   - CNN vs LLM → **不同技术栈，不合并**

3. **判断应用领域**（解决什么问题/什么场景）是否相同：
   - 医学影像分割 / 医学影像分类 → 相同领域
   - 医学影像 / 医学（泛指）→ **粒度不同，不合并**
   - 情感分析 / 文本分类 → 相同领域（NLP 应用）
   - 医学影像 / 遥感影像 → **不同领域，不合并**

4. **Examples**:

   | 已有 topic | 新查询 | 合并？ | 理由 |
   |---|---|---|---|
   | 卷积神经网络医学影像 | cnn 医学影像综述 | ✅ 合并 | CNN + 医学影像，技术和领域均相同 |
   | 医学影像分割 | unet 医学影像分割 | ✅ 合并 | 技术不同但应用领域都是医学影像分割 |
   | transformer 医学影像 | llm 医学应用 | ❌ 不合并 | transformer vs llm 技术不同，医学影像 vs 医学领域粒度也不同 |
   | 自然语言处理 | transformer 情感分析 | ❌ 不合并 | NLP 应用 vs 具体 transformer 技术，粒度不匹配（除非 query 是 "nlp 综述" 类） |
   | federated learning | 联邦学习医疗应用 | ✅ 合并 | 技术相同（联邦学习），领域为医疗 |

5. **New topics**: only create a new topic when the query is genuinely unrelated
   to all existing topics, OR when the technique or application area diverges
   significantly from any existing topic.

### How to invoke

- **Merge explicitly** (preferred): pass `--merge-into <slug>` when you've
  identified a match
  ```
  python3 -m cli.main search --topic "..." --merge-into existing-slug
  ```
- **New topic**: pass `--new-topic` when truly new (overrides auto-detect)
  ```
  python3 -m cli.main search --topic "..." --new-topic
  ```
- **Auto (rule fallback)**: omit both flags — `core/merger.py` handles it,
  less accurate but functional

## Behavior

1. Parses natural language input to detect intent (search / download / list)
2. Maps to CLI subcommands via `python3 -m cli.main`
3. Auto-installs missing dependencies on first run
4. Search: queries multiple sources, deduplicates, saves as markdown table.
   Before searching, do LLM-based topic matching (see Topic Management above)
5. Download: reads results, fetches PDFs from Sci-Hub
6. List: shows all saved topics with paper counts

## Environment

The skill uses Python's built-in virtual environment (venv).
On first run, `skill.py` auto-creates `.venv` in the project root
and installs dependencies into it.

You can also set up manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

No external environment manager (conda, pyenv-virtualenv, etc.) is required.
