# Refactor: Remove Scholar + Rewrite Semantic Scholar with SDK — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Google Scholar search source and all proxy code, rewrite Semantic Scholar source to use the `semanticscholar` SDK instead of raw REST API calls.

**Architecture:** Replace `core/sources/semantic.py`'s raw `requests.get` calls to the Semantic Scholar REST API with the `semanticscholar` Python SDK. Delete `core/sources/scholar.py` and `core/proxy.py` entirely. Remove `proxy_manager` parameter plumbing from downloader and searcher. Clean config, CLI defaults, SKILL.md, and tests.

**Tech Stack:** Python 3.10+, `semanticscholar>=0.8`, `requests`, `pyyaml`

---

### Task 1: Update package dependencies

**Files:**
- Modify: `pyproject.toml:10-17`
- Modify: `skill.py:27-36`

- [ ] **Step 1: Replace scholarly/httpx with semanticscholar in pyproject.toml**

In `pyproject.toml`, replace the two lines:

```
    "scholarly>=1.7",
    "httpx<0.28",
```

with:

```
    "semanticscholar>=0.8",
```

Use Edit to remove the `scholarly` and `httpx` lines and add `semanticscholar`.

- [ ] **Step 2: Update REQUIRED_IMPORTS in skill.py**

In `skill.py`, change:

```python
_REQUIRED_IMPORTS = {
    "requests": "requests",
    "pyyaml": "yaml",
    "rapidfuzz": "rapidfuzz",
    "beautifulsoup4": "bs4",
    "scholarly": "scholarly",
    "arxiv": "arxiv",
    "questionary": "questionary",
    "rich": "rich",
}
```

to:

```python
_REQUIRED_IMPORTS = {
    "requests": "requests",
    "pyyaml": "yaml",
    "rapidfuzz": "rapidfuzz",
    "beautifulsoup4": "bs4",
    "semanticscholar": "semanticscholar",
    "arxiv": "arxiv",
    "questionary": "questionary",
    "rich": "rich",
}
```

- [ ] **Step 3: Install new dependency and verify**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/pip install semanticscholar>=0.8
```

Expected: installs successfully.

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -c "from semanticscholar import SemanticScholar; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml skill.py
git commit -m "chore: replace scholarly/httpx with semanticscholar dependency"
```

---

### Task 2: Rewrite SemanticSource with SDK + update tests

**Files:**
- Modify: `core/sources/semantic.py`
- Modify: `tests/test_sources.py:65-122`

- [ ] **Step 1: Write the new failing tests for SemanticSource with SDK**

In `tests/test_sources.py`, replace the entire "Semantic Scholar tests" section (lines 65-122, from `# --- Semantic Scholar tests ---` through the end of `test_semantic_search_error`) with:

```python
# --- Semantic Scholar tests (SDK) ---

from unittest.mock import patch, MagicMock
from semanticscholar.Paper import Paper as S2Paper
from semanticscholar.Author import Author as S2Author


def _fake_s2_paper(title="Test Paper", authors=None, year=2024,
                   doi=None, arxiv_id=None, citation_count=0,
                   paper_id="abc123", url=None, abstract=""):
    """Build a fake semanticscholar.Paper object."""
    p = MagicMock(spec=S2Paper)
    p.title = title
    p.authors = [S2Author({"authorId": "1", "name": a}) for a in (authors or ["Smith, J."])]
    p.year = year
    p.externalIds = {}
    if doi:
        p.externalIds["DOI"] = doi
    if arxiv_id:
        p.externalIds["ArXiv"] = arxiv_id
    p.citationCount = citation_count
    p.paperId = paper_id
    p.url = url or f"https://api.semanticscholar.org/paper/{paper_id}"
    p.abstract = abstract
    return p


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_returns_papers(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(
            title="Deep Learning Review",
            authors=["Yann LeCun", "Yoshua Bengio"],
            year=2015,
            doi="10.1038/nature14539",
            citation_count=50000,
        )
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("deep learning", max_results=10)

    assert len(papers) == 1
    assert papers[0].title == "Deep Learning Review"
    assert papers[0].authors == ["Yann LeCun", "Yoshua Bengio"]
    assert papers[0].citations == 50000
    assert papers[0].doi == "10.1038/nature14539"
    assert papers[0].source == "semantic"
    mock_client.search_paper.assert_called_once_with(
        "deep learning",
        limit=10,
        fields=["title", "authors", "year", "externalIds", "citationCount", "url", "abstract"],
    )


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_missing_fields(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(title="Unknown Paper", authors=None, year=None,
                       doi=None, citation_count=None, abstract=None, url=None)
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)

    assert len(papers) == 1
    assert papers[0].title == "Unknown Paper"
    assert papers[0].authors == []
    assert papers[0].doi is None
    assert papers[0].date is None
    assert papers[0].citations is None


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_with_arxiv_id(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(
            title="ArXiv Paper",
            authors=["Jones, K."],
            year=2023,
            arxiv_id="2301.12345",
        )
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)

    assert len(papers) == 1
    assert papers[0].eprint_url == "https://arxiv.org/abs/2301.12345"


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = []
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("nonexistent", max_results=10)
    assert papers == []


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.side_effect = Exception("API error")
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)
    assert papers == []


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_with_api_key(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = []
    mock_client_cls.return_value = mock_client

    source = SemanticSource(api_key="test-key-123", delay_min=0, delay_max=0)
    source.search("test", max_results=10)

    mock_client_cls.assert_called_once_with(api_key="test-key-123")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/test_sources.py -k "semantic" -v
```

Expected: tests fail — `ModuleNotFoundError: No module named 'semanticscholar'` or `AttributeError` on the old implementation.

- [ ] **Step 3: Rewrite core/sources/semantic.py**

Write the entire file:

```python
import logging
from datetime import date as dt_date
from semanticscholar import SemanticScholar
from core.sources.base import BaseSource
from core.models import Paper

logger = logging.getLogger(__name__)


class SemanticSource(BaseSource):
    name = "semantic"

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.client = SemanticScholar(api_key=api_key)

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        try:
            self.limiter.wait()
            results = self.client.search_paper(
                topic,
                limit=max_results,
                fields=[
                    "title", "authors", "year", "externalIds",
                    "citationCount", "url", "abstract",
                ],
            )
        except Exception as exc:
            logger.warning("Semantic Scholar API error: %s", exc)
            return []

        papers = []
        for paper in results:
            ext_ids = paper.externalIds or {}
            papers.append(Paper(
                title=paper.title or "",
                authors=[a.name for a in paper.authors] if paper.authors else [],
                date=dt_date(paper.year, 1, 1) if paper.year else None,
                doi=ext_ids.get("DOI"),
                citations=paper.citationCount,
                source=self.name,
                url=paper.url or "",
                abstract=(paper.abstract or "").strip(),
                pub_url=paper.url or "",
                eprint_url=(
                    f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
                    if ext_ids.get("ArXiv") else ""
                ),
            ))
        return papers
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/test_sources.py -k "semantic" -v
```

Expected: all 6 semantic tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: arxiv tests pass. Scholar tests may fail (will be removed in Task 3). Proxy tests may fail (will be removed in Task 3). Semantic tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/sources/semantic.py tests/test_sources.py
git commit -m "refactor: rewrite SemanticSource with semanticscholar SDK"
```

---

### Task 3: Remove Scholar source

**Files:**
- Delete: `core/sources/scholar.py`
- Modify: `tests/test_sources.py` (remove scholar tests and imports)

- [ ] **Step 1: Delete scholar.py and remove scholar imports from tests**

Delete `core/sources/scholar.py`:

```bash
cd /Users/matthewtan/project/python/ccbTest && rm core/sources/scholar.py
```

In `tests/test_sources.py`, remove the import line:

```python
from core.sources.scholar import ScholarSource
```

- [ ] **Step 2: Remove all Scholar test functions from test_sources.py**

Remove these functions from `tests/test_sources.py`:
- `_fake_scholarly_pub` (helper)
- `test_scholar_search`
- `test_scholar_search_error_fallback`
- `test_scholar_search_with_proxy_manager_setup`
- `test_scholar_search_without_proxy_manager_backward_compat`
- `test_scholar_search_auto_mode_no_static_uses_free_preemptively`
- `test_scholar_search_rate_limited_switches_proxy`
- `test_scholar_search_network_error_does_not_switch_proxy`

Also remove the unused import at the top if any remain:
```python
from unittest.mock import patch, MagicMock
```
(keep this — it's used by semantic and arxiv tests)

Remove the comment lines:
- `# --- Scholar tests ---`
- `# --- Scholar proxy integration tests ---`

- [ ] **Step 3: Remove scholar from core/searcher.py**

In `core/searcher.py`:
- Remove `from core.sources.scholar import ScholarSource` (line 10)
- Remove `"scholar": ScholarSource,` from SOURCE_CLASSES (line 17)
- Remove the `if src_name == "scholar" and proxy_manager:` block (lines 205-206) including `kwargs["proxy_manager"] = proxy_manager`
- Change default `sources` from `["semantic", "arxiv", "scholar"]` to `["semantic", "arxiv"]` in the `search()` function signature (line 182)
- Remove `proxy_manager=None` from `search()` function signature (line 182)

- [ ] **Step 4: Remove scholar from test_searcher.py**

In `tests/test_searcher.py`, remove `test_deduplicate_cross_key` function (the one that references `source="scholar"`) and its comment.

In `test_deduplicate_multiple_in_group`, change the third paper from `source="scholar"` to `source="semantic"`.

- [ ] **Step 5: Run remaining tests to verify**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/test_sources.py tests/test_searcher.py -v
```

Expected: all remaining tests PASS. No scholar import errors.

- [ ] **Step 6: Commit**

```bash
git add core/sources/scholar.py core/searcher.py tests/test_sources.py tests/test_searcher.py
git commit -m "refactor: remove Scholar search source"
```

---

### Task 4: Remove proxy code

**Files:**
- Delete: `core/proxy.py`
- Delete: `tests/test_proxy.py`
- Modify: `core/downloader.py`
- Modify: `tests/test_downloader.py`
- Modify: `cli/search.py`
- Modify: `cli/download.py`

- [ ] **Step 1: Delete proxy files**

```bash
cd /Users/matthewtan/project/python/ccbTest && rm core/proxy.py tests/test_proxy.py
```

- [ ] **Step 2: Remove proxy_manager from core/downloader.py**

In `_Downloader.__init__`, change the signature and body:

Old:
```python
    def __init__(self, domains: list[str], timeout: int = 60, proxy_manager=None):
        if not domains:
            raise ValueError("domains parameter is required")
        self.domains = domains
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": _USER_AGENT})
        if proxy_manager:
            proxy_manager.configure_session(self.sess)
        self._available_domains = list(domains)
        self._probed = False
```

New:
```python
    def __init__(self, domains: list[str], timeout: int = 60):
        if not domains:
            raise ValueError("domains parameter is required")
        self.domains = domains
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": _USER_AGENT})
        self._available_domains = list(domains)
        self._probed = False
```

In the public `download()` function, change:

Old:
```python
def download(
    paper: Paper,
    output_dir: Path,
    domains: list[str],
    timeout: int = 60,
    proxy_manager=None,
) -> Optional[Path]:
    """Download a paper from Sci-Hub."""
    dl = _Downloader(domains, timeout, proxy_manager=proxy_manager)
    try:
        return dl.fetch_pdf(paper, output_dir)
    finally:
        dl.close()
```

New:
```python
def download(
    paper: Paper,
    output_dir: Path,
    domains: list[str],
    timeout: int = 60,
) -> Optional[Path]:
    """Download a paper from Sci-Hub."""
    dl = _Downloader(domains, timeout)
    try:
        return dl.fetch_pdf(paper, output_dir)
    finally:
        dl.close()
```

- [ ] **Step 3: Remove proxy tests from test_downloader.py**

Remove the entire `TestDownloaderProxy` class (including `test_downloader_with_proxy_manager_configures_session` and `test_downloader_without_proxy_manager_backward_compat`).

Also remove the import:
```python
from core.proxy import ProxyManager
```
(if present — it may be inside the test function rather than at the top)

- [ ] **Step 4: Remove ProxyManager from cli/search.py**

In `cli/search.py`:
- Remove `from core.proxy import ProxyManager` (line 6)
- In `run(args)`, remove `proxy_mgr = ProxyManager(config)` (line 13)
- In the `core_search()` call, remove `proxy_manager=proxy_mgr` (line 43)

- [ ] **Step 5: Remove ProxyManager from cli/download.py**

In `cli/download.py`:
- Remove `from core.proxy import ProxyManager` (line 5)
- In `run(args)`, remove `proxy_mgr = ProxyManager(config)` (line 44)
- In the `download()` call, remove `proxy_manager=proxy_mgr` (line 103)

- [ ] **Step 6: Run tests to verify**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/test_downloader.py tests/test_sources.py tests/test_searcher.py -v
```

Expected: all remaining tests PASS. No proxy import errors.

- [ ] **Step 7: Commit**

```bash
git add core/proxy.py tests/test_proxy.py core/downloader.py tests/test_downloader.py cli/search.py cli/download.py
git commit -m "refactor: remove ProxyManager and all proxy-related code"
```

---

### Task 5: Clean up config and CLI defaults

**Files:**
- Modify: `core/config.py`
- Modify: `config.example.yaml`
- Modify: `cli/main.py`

- [ ] **Step 1: Remove scholar and proxy from core/config.py**

In `core/config.py`, update `DEFAULT_CONFIG`:

Old:
```python
DEFAULT_CONFIG = {
    "sources": {
        "scholar": {
            "enabled": True,
            "delay_min": 10,
            "delay_max": 20,
        },
        "arxiv": {"enabled": True, "delay_min": 1, "delay_max": 3},
        "semantic": {"enabled": True, "delay_min": 0.5, "delay_max": 1.5, "api_key": None},
    },
    "pip_mirror": None,
    "download": {
        "scihub_domains": DEFAULT_SCIHUB_DOMAINS.copy(),
        "timeout": 60,
    },
    "proxy": {"http": None, "https": None, "free_mode": "auto"},
    "storage": {"base_dir": "./papers"},
}
```

New:
```python
DEFAULT_CONFIG = {
    "sources": {
        "arxiv": {"enabled": True, "delay_min": 1, "delay_max": 3},
        "semantic": {"enabled": True, "delay_min": 0.5, "delay_max": 1.5, "api_key": None},
    },
    "pip_mirror": None,
    "download": {
        "scihub_domains": DEFAULT_SCIHUB_DOMAINS.copy(),
        "timeout": 60,
    },
    "storage": {"base_dir": "./papers"},
}
```

- [ ] **Step 2: Remove scholar and proxy from config.example.yaml**

In `config.example.yaml`, delete the scholar source block:

```yaml
  scholar:
    enabled: true
    delay_min: 10
    delay_max: 20
```

And delete the proxy block:

```yaml
proxy:
  http: null
  https: null
  free_mode: auto  # auto | on | off — when to use free proxies for Scholar/requests
```

The resulting file should start with:

```yaml
sources:
  arxiv:
    enabled: true
    delay_min: 1
    delay_max: 3
  semantic:
    enabled: true
    delay_min: 0.5
    delay_max: 1.5
    api_key: null  # Optional: get a free key at https://www.semanticscholar.org/product/api#api-key-form

download:
  scihub_domains:
    - https://sci-hub.se
    - https://sci-hub.st
    - https://sci-hub.ru
  timeout: 60

# Optional: pip install mirror for faster dependency installation in restricted regions.
# Example: https://pypi.tuna.tsinghua.edu.cn/simple
# When unset or null, pip uses the official PyPI index.
pip_mirror: null

storage:
  base_dir: ./papers
```

- [ ] **Step 3: Update CLI default sources in cli/main.py**

In `cli/main.py`, change:

```python
p_search.add_argument("--sources", "-s", default="semantic,arxiv,scholar",
                      help="Comma-separated sources (default: semantic,arxiv,scholar)")
```

to:

```python
p_search.add_argument("--sources", "-s", default="semantic,arxiv",
                      help="Comma-separated sources (default: semantic,arxiv)")
```

- [ ] **Step 4: Run tests to verify**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/test_config.py -v
```

Expected: config tests PASS.

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -c "
from core.config import load_config, DEFAULT_CONFIG
assert 'scholar' not in DEFAULT_CONFIG['sources']
assert 'proxy' not in DEFAULT_CONFIG
print('OK: config clean')
"
```

Expected: `OK: config clean`

- [ ] **Step 5: Commit**

```bash
git add core/config.py config.example.yaml cli/main.py
git commit -m "refactor: remove scholar and proxy from config and CLI defaults"
```

---

### Task 6: Update SKILL.md

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Update descriptions and trigger words**

In `SKILL.md`:

Line 2: Change
```
Search academic papers across Google Scholar, arXiv, and Semantic Scholar, save results to markdown files, and download papers from Sci-Hub.
```
to
```
Search academic papers across arXiv and Semantic Scholar, save results to markdown files, and download papers from Sci-Hub.
```

Line 24-30 (Triggers section): Remove the line `- google scholar` from the trigger list.

Line 114 (manual setup): Change
```
.venv/bin/pip install requests pyyaml rapidfuzz beautifulsoup4 scholarly arxiv questionary rich
```
to
```
.venv/bin/pip install requests pyyaml rapidfuzz beautifulsoup4 semanticscholar arxiv questionary rich
```

Line 88 (timeout tip): Change
```
print("[paper-fetcher] Tip: Google Scholar is often rate-limited. Try '--sources semantic,arxiv'")
```
to
```
print("[paper-fetcher] Tip: The request took too long. Try with fewer sources.")
```

- [ ] **Step 2: Verify no remaining scholar/scholarly/Google Scholar references**

```bash
cd /Users/matthewtan/project/python/ccbTest && grep -in "scholar\|scholarly\|google scholar\|proxy" SKILL.md
```

Expected: no matches (except possibly in the manual setup command where we already fixed it).

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "docs: update SKILL.md for scholar removal and SDK switch"
```

---

### Task 7: Integration verification

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -m pytest tests/ -v
```

Expected: all tests PASS. No import errors.

- [ ] **Step 2: Verify no residual imports**

```bash
cd /Users/matthewtan/project/python/ccbTest && grep -r "scholarly\|from scholarly\|import scholarly\|\"scholar\"\|'scholar'\|ScholarSource\|proxy_manager\|ProxyManager\|from core.proxy\|import core.proxy" core/ cli/ tests/ skill.py --include="*.py"
```

Expected: no output.

- [ ] **Step 3: Verify import of all modules**

```bash
cd /Users/matthewtan/project/python/ccbTest && .venv/bin/python -c "
from core.models import Paper
from core.sources.base import BaseSource
from core.sources.semantic import SemanticSource
from core.sources.arxiv import ArxivSource
from core.searcher import search, deduplicate
from core.config import load_config
from core.downloader import download, _Downloader
from core.storage import save_results, parse_results, load_index
from core.merger import find_similar_topic
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 4: Commit verification**

```bash
git add -A && git diff --cached --stat
```

Only expected files should be staged. No unintended files.

```bash
git commit -m "chore: final integration verification"
```
