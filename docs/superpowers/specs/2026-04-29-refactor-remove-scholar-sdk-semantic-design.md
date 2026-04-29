# Refactor: Remove Scholar + Rewrite Semantic Scholar with SDK

## 目标

1. 删除 Google Scholar 搜索源及相关代码
2. 移除 `scholarly` 依赖（含 `httpx` 版本锁定）
3. 删除所有代理相关代码（ProxyManager、proxy 配置、free_mode）
4. 重写 `SemanticSource`，从原始 REST API 改为 `semanticscholar` SDK
5. 同步更新 SKILL.md 文档

## 架构变更

```
删除:
  core/sources/scholar.py          ← Google Scholar 搜索源
  core/proxy.py                    ← 代理管理器（仅服务于 scholarly）
  tests/test_proxy.py              ← 代理测试

修改:
  其余文件见下文详细清单
```

搜索栈变为双源：semantic + arxiv（原为三源）。

## 文件变更清单

### 删除

| 文件 | 说明 |
|------|------|
| `core/sources/scholar.py` | Scholar 搜索源 |
| `core/proxy.py` | ProxyManager，FreeProxies/setup_scholarly 等 |
| `tests/test_proxy.py` | 14 个 proxy 测试 |

### 包依赖

| 文件 | 变更 |
|------|------|
| `pyproject.toml` | `scholarly>=1.7` + `httpx<0.28` → `semanticscholar>=0.8` |
| `skill.py` | `_REQUIRED_IMPORTS`: `scholarly` → `semanticscholar`，移除 `httpx` |

### Core 模块

| 文件 | 变更 |
|------|------|
| `core/sources/scholar.py` | 删除 |
| `core/proxy.py` | 删除 |
| `core/sources/semantic.py` | REST API → `semanticscholar` SDK |
| `core/searcher.py` | 移除 scholar 源、proxy_manager 参数，默认 sources → `["semantic", "arxiv"]` |
| `core/config.py` | DEFAULT_CONFIG 删除 `sources.scholar` 和 `proxy` 段 |
| `core/downloader.py` | `_Downloader.__init__` 和 `download()` 移除 `proxy_manager` 参数 |

### 配置

| 文件 | 变更 |
|------|------|
| `config.example.yaml` | 移除 `sources.scholar` 段和 `proxy` 段 |
| `config.yaml` | 用户手动更新或自动 merge 时去掉旧 key |

### CLI

| 文件 | 变更 |
|------|------|
| `cli/main.py` | 默认 `--sources` 从 `semantic,arxiv,scholar` → `semantic,arxiv` |
| `cli/search.py` | 移除 `ProxyManager` import 和调用 |
| `cli/download.py` | 移除 `ProxyManager` import 和调用 |

### 测试

| 文件 | 变更 |
|------|------|
| `tests/test_sources.py` | 移除所有 scholar 测试函数，重写 semantic 测试（mock SDK 而非 requests.get） |
| `tests/test_downloader.py` | 移除 `TestDownloaderProxy` 类 |
| `tests/test_searcher.py` | 移除 `test_deduplicate_cross_key` 中的 scholar 引用 |

### 文档

| 文件 | 变更 |
|------|------|
| `SKILL.md` | 描述中去掉 Google Scholar；触发词去掉 "google scholar"；环境说明 `scholarly` → `semanticscholar` |

## SemanticSource 重写细节

### 当前实现（REST API）

```python
import requests
BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

def search(self, topic, max_results):
    resp = self._request_with_retry(self.BASE_URL, params={...}, headers=...)
    data = resp.json()
    for item in data.get("data", []):
        # parse item → Paper
```

### 新实现（SDK）

```python
from semanticscholar import SemanticScholar

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
                fields=["title", "authors", "year", "externalIds",
                        "citationCount", "url", "abstract"],
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

SDK 内部处理重试和 rate limit，不再调用 `_request_with_retry`。但仍然使用 `self.limiter.wait()` 保持调用间隔控制。

## Config 变更

### DEFAULT_CONFIG 变更

旧：
```python
DEFAULT_CONFIG = {
    "sources": {
        "scholar": {"enabled": True, "delay_min": 10, "delay_max": 20},
        "arxiv": {"enabled": True, "delay_min": 1, "delay_max": 3},
        "semantic": {"enabled": True, "delay_min": 0.5, "delay_max": 1.5, "api_key": None},
    },
    "proxy": {"http": None, "https": None, "free_mode": "auto"},
    ...
}
```

新：
```python
DEFAULT_CONFIG = {
    "sources": {
        "arxiv": {"enabled": True, "delay_min": 1, "delay_max": 3},
        "semantic": {"enabled": True, "delay_min": 0.5, "delay_max": 1.5, "api_key": None},
    },
    "pip_mirror": None,
    "download": {"scihub_domains": ..., "timeout": 60},
    "storage": {"base_dir": "./papers"},
}
```

### config.example.yaml 变更

删除整个 `sources.scholar` 段和 `proxy` 段。

## CLI 变更

- `cli/main.py`: `--sources` default → `"semantic,arxiv"`
- `cli/search.py` `run()`: 移除 `from core.proxy import ProxyManager` 和 `proxy_mgr = ProxyManager(config)` 及相关传参
- `cli/download.py` `run()`: 同上，移除 ProxyManager

## Downloader 变更

- `_Downloader.__init__`: 移除 `proxy_manager` 参数及 `if proxy_manager: proxy_manager.configure_session(self.sess)`
- `download()`: 移除 `proxy_manager` 参数

## Searcher 变更

- `search()`: 移除 `proxy_manager` 参数
- `SOURCE_CLASSES`: 移除 `"scholar": ScholarSource` 和对应的 import
- 默认 sources: `["semantic", "arxiv"]`
- scholar 的 kwargs 分支删除

## SKILL.md 变更

- 描述: "across Google Scholar, arXiv, and Semantic Scholar" → "across arXiv and Semantic Scholar"
- 触发词: 删除 "google scholar"
- 环境说明: `scholarly` → `semanticscholar`
- 超时提示: 删除 "Google Scholar is often rate-limited" 相关

## 错误处理

- Semantic Scholar API 异常：返回空列表（与现有行为一致）
- SDK 内部已处理 rate limit 和重试，无需额外处理
- 现有 `_request_with_retry` 保留在 BaseSource 中（arXiv 仍通过 arxiv 包调用，但 base 方法保留供未来使用）
- _deep_merge 会自动忽略 config.yaml 中的旧 key（scholar, proxy），向后兼容

## 测试要点

| 场景 | 说明 |
|------|------|
| Semantic Scholar 正常搜索 | mock SDK client 返回 Paper 对象列表 |
| Semantic Scholar API 异常 | mock SDK 抛异常，验证返回 [] |
| Semantic Scholar 缺失字段 | title=None, authors=[], year=None 等情况 |
| arxiv 源不受影响 | 现有 arxiv 测试保持不变 |
| 去重 | 移除 scholar 相关的 cross-key 测试，其他去重测试保持 |
| Downloader 无 proxy | 移除 proxy 测试，现有下载测试保持 |
| 导入验证 | 无 scholarly/proxy 导入残留 |
| SKILL.md | 无 "scholar"/"scholarly"/"Google Scholar" 残留 |

## 不在范围内

- Semantic Scholar author/reference API（确认只保留 search）
- 任何新的代理/限流机制
- 非 scholar 源的功能增强
