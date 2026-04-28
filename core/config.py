import os
import shutil
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
    "proxy": {"http": None, "https": None, "free_mode": "auto"},
    "storage": {"base_dir": "./papers"},
}


def ensure_config():
    """Auto-create config.yaml from config.example.yaml on first run."""
    config = Path("config.yaml")
    example = Path("config.example.yaml")
    if not config.exists() and example.exists():
        shutil.copy2(example, config)
        print("[config] Created config.yaml from config.example.yaml — edit it to customize settings.")


def load_config(path: Path | None = None) -> dict:
    ensure_config()
    candidate = path or Path("config.yaml")
    if candidate.exists():
        with open(candidate) as f:
            user = yaml.safe_load(f) or {}
        config = _deep_merge(DEFAULT_CONFIG, user)
    else:
        config = DEFAULT_CONFIG.copy()

    # When invoked via an agent (Skill tool), resolve relative base_dir
    # against the launch CWD, not the skill's installation directory.
    launch_cwd = os.environ.get("PAPER_FETCHER_CWD")
    if launch_cwd:
        base = config.get("storage", {}).get("base_dir", "./papers")
        p = Path(base)
        if not p.is_absolute():
            config["storage"]["base_dir"] = str(Path(launch_cwd) / p)

    return config


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
