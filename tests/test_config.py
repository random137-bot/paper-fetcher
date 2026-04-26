"""Tests for config path resolution with PAPER_FETCHER_CWD env var."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def _make_config(tmp: str, base_dir: str = "./papers") -> Path:
    """Write a minimal config.yaml and return its path."""
    cfg = Path(tmp) / "config.yaml"
    cfg.write_text(f"storage:\n  base_dir: {base_dir}\n")
    return cfg


def test_base_dir_resolved_against_env_var():
    """PAPER_FETCHER_CWD causes relative base_dir to resolve against it."""
    from core.config import load_config

    with tempfile.TemporaryDirectory() as launch_cwd:
        config_dir = Path(launch_cwd) / "config"
        config_dir.mkdir()
        _make_config(str(config_dir))

        with patch.dict(os.environ, {"PAPER_FETCHER_CWD": launch_cwd}, clear=False):
            config = load_config(config_dir / "config.yaml")
            expected = str(Path(launch_cwd) / "papers")
            assert config["storage"]["base_dir"] == expected, (
                f"Expected {expected}, got {config['storage']['base_dir']}"
            )


def test_base_dir_unchanged_without_env_var():
    """Without PAPER_FETCHER_CWD, relative base_dir is used as-is."""
    from core.config import load_config

    with tempfile.TemporaryDirectory() as tmp:
        config_path = _make_config(tmp)

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_path)
            assert config["storage"]["base_dir"] == "./papers", (
                f"Expected './papers', got {config['storage']['base_dir']}"
            )


def test_absolute_base_dir_unaffected_by_env():
    """Absolute base_dir should not be changed by PAPER_FETCHER_CWD."""
    from core.config import load_config

    with tempfile.TemporaryDirectory() as tmp:
        config_path = _make_config(tmp, base_dir="/absolute/papers")

        with patch.dict(os.environ, {"PAPER_FETCHER_CWD": "/some/launch"}, clear=False):
            config = load_config(config_path)
            assert config["storage"]["base_dir"] == "/absolute/papers", (
                f"Expected '/absolute/papers', got {config['storage']['base_dir']}"
            )


def test_env_var_applies_to_default_config():
    """When no config.yaml exists, DEFAULT_CONFIG base_dir still resolves."""
    from core.config import load_config

    with tempfile.TemporaryDirectory() as launch_cwd:
        with patch.dict(os.environ, {"PAPER_FETCHER_CWD": launch_cwd}, clear=False):
            config = load_config(Path("/nonexistent/config.yaml"))
            expected = str(Path(launch_cwd) / "papers")
            assert config["storage"]["base_dir"] == expected, (
                f"Expected {expected}, got {config['storage']['base_dir']}"
            )


def test_env_var_with_subdirectory_base():
    """base_dir with subdirectory structure resolves correctly."""
    from core.config import load_config

    with tempfile.TemporaryDirectory() as launch_cwd:
        config_dir = Path(launch_cwd) / "config"
        config_dir.mkdir()
        _make_config(str(config_dir), base_dir="./output/saved-papers")

        with patch.dict(os.environ, {"PAPER_FETCHER_CWD": launch_cwd}, clear=False):
            config = load_config(config_dir / "config.yaml")
            expected = str(Path(launch_cwd) / "output" / "saved-papers")
            assert config["storage"]["base_dir"] == expected, (
                f"Expected {expected}, got {config['storage']['base_dir']}"
            )
