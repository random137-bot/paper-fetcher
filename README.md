# Paper Fetcher

<p>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
  <a href="https://claude.ai/code"><img alt="Claude Code" src="https://img.shields.io/badge/Claude%20Code-ready-black?logo=anthropic"></a>
</p>

> Search academic papers across multiple sources and download PDFs — all from natural language in Claude Code.

[**English**](README.md) | [**中文**](README.zh.md)

---

## Features

- **Multi-source search** — queries Semantic Scholar API, arXiv, and Google Scholar simultaneously
- **Smart dedup** — merges results by DOI + title + author, keeps the richest version
- **Auto PDF download** — arXiv direct → Sci-Hub multi-domain fallback → direct URL, with exponential backoff
- **Topic management** — LLM-guided merging groups related searches by technique + application domain
- **Bilingual** — full Chinese (中文) and English query support
- **Zero-config bootstrap** — auto-creates venv and installs dependencies on first run

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- [**Claude Code**](https://claude.ai/code)

### Install as a Claude Code skill

```bash
claude skill add paper-fetcher https://github.com/random137-bot/paper-fetcher.git
```

### Or run standalone

```bash
git clone https://github.com/random137-bot/paper-fetcher.git
cd paper-fetcher
python3 skill.py help
```

---

## Usage

### In Claude Code (natural language)

```
search papers on federated learning
download papers from my federated learning results
show my saved topics
find papers about causal inference
sci-hub download deep learning papers

搜索机器学习的论文
下载深度学习相关的论文
列出已保存的主题
```

### From the command line

```bash
# Search
python3 -m cli.main search --topic "transformer attention" --max 30

# Search with explicit merge into existing topic
python3 -m cli.main search --topic "医学影像分割" --merge-into medical-image-segmentation

# Search as new topic (skip auto-merge)
python3 -m cli.main search --topic "reinforcement learning" --new-topic

# Download all pending papers
python3 -m cli.main download --topic "federated-learning" --all

# List saved topics
python3 -m cli.main list
```

### Skill entry point

```bash
python3 skill.py search federated learning
python3 skill.py download deep learning
python3 skill.py list
python3 skill.py help
```

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
sources:
  scholar:
    enabled: true
    delay_min: 10
    delay_max: 20
  semantic:
    enabled: true
    api_key: YOUR_SEMANTIC_SCHOLAR_KEY  # Optional, get a free key from Semantic Scholar
download:
  scihub_domains:
    - https://sci-hub.se
    - https://sci-hub.st
proxy:
  http: null
  https: null
storage:
  base_dir: ./papers
```

---

## Architecture

```
skill.py          ← NLP intent parser (search/download/list), auto-bootstrap
cli/main.py       ← argparse CLI entry point
core/
├── searcher.py   ← Multi-source orchestration, dedup, Crossref DOI enrichment
├── merger.py     ← Fuzzy topic matching (used when --merge-into not specified)
├── downloader.py ← arXiv direct → Sci-Hub BS4 extraction → direct URL fallback
├── storage.py    ← results.md + papers.json persistence, .index.json index
├── models.py     ← Paper & TopicInfo dataclasses
├── config.py     ← YAML config with deep-merge defaults
└── sources/
    ├── base.py      ← Abstract source with rate limiter + retry
    ├── arxiv.py     ← arXiv API client
    ├── semantic.py  ← Semantic Scholar API client
    └── scholar.py   ← Google Scholar (via scholarly)
```

### Topic merging logic

Paper Fetcher uses **LLM-guided semantic merging** (not keyword overlap) to decide if a new search should fold into an existing topic directory. The rule:

> **Same technique + same application domain** = merge.
> Different technique or different domain/scope = new topic.

See `SKILL.md` for the full decision table.

---

## Data storage

Results are saved under `./papers/<topic-slug>/`:

```
papers/
├── .index.json          ← Topic index
├── federated-learning/
│   ├── results.md       ← Search results table
│   └── papers.json      ← Full metadata (abstract, URLs, DOIs)
├── medical-image-cnn/
│   ├── results.md
│   ├── papers.json
│   └── 2024-03-01 U-Net Medical Segmentation.pdf
└── ...
```

---

## Development

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or let skill.py auto-install

# Run tests
python3 -m pytest tests/ -v
```

---

## License

**MIT** — see [LICENSE](LICENSE).
