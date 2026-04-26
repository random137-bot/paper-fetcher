import yaml
from pathlib import Path

# 默认 Sci-Hub 域名列表，作为单一数据源
DEFAULT_SCIHUB_DOMAINS = [
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
]

DEFAULT_CONFIG = {
    "sources": {
        "scholar": {
            "enabled": True,
            "delay_min": 10,
            "delay_max": 20,
            "cookie_file": "~/.paper-fetcher/scholar.cookies",
        },
        "arxiv": {"enabled": True, "delay_min": 1, "delay_max": 3},
        "semantic": {"enabled": True, "delay_min": 0.5, "delay_max": 1.5, "api_key": None},
    },
    "pip_mirror": None,
    "download": {
        "scihub_domains": DEFAULT_SCIHUB_DOMAINS.copy(),
        "timeout": 60,
    },
    "proxy": {"http": None, "https": None},
    "storage": {"base_dir": "./papers"},
}


def load_config(path: Path | None = None) -> dict:
    if path is not None and path.exists():
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, user)
    return DEFAULT_CONFIG.copy()


def _deep_merge(base: dict, override: dict) -> dict:
    result = {}
    for k, v in base.items():
        if k in override and isinstance(v, dict) and isinstance(override[k], dict):
            result[k] = _deep_merge(v, override[k])
        elif k in override:
            result[k] = override[k]
        else:
            result[k] = v
    for k, v in override.items():
        if k not in base:
            result[k] = v
    return result
