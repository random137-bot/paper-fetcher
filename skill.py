#!/usr/bin/env python3
"""
Paper Fetcher Skill -- natural language interface to the papers CLI.
Parses user intent from natural language and dispatches to CLI subcommands.

On first run in a new environment, auto-bootstraps dependencies via pip.
"""
import re
import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")

# ---------------------------------------------------------------------------
# Bootstrap: ensure required packages are installed inside a project-local
# virtual environment (venv), avoiding any dependency on conda or global pip.
# ---------------------------------------------------------------------------

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


def _in_project_venv() -> bool:
    """Return True if already running inside the project's .venv."""
    venv = os.environ.get("VIRTUAL_ENV", "")
    return os.path.realpath(venv) == os.path.realpath(VENV_DIR)


def _venv_python() -> str:
    """Path to the python binary inside the project venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _ensure_venv():
    """Create the project venv if it does not exist yet."""
    if os.path.isdir(VENV_DIR):
        return
    print(f"[paper-fetcher] Creating virtual environment at {VENV_DIR} ...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", VENV_DIR],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print("[paper-fetcher] Failed to create venv:", result.stderr)
        sys.exit(1)


def _load_pip_mirror() -> str | None:
    """Read pip mirror from config.yaml (if set) without requiring yaml dep."""
    config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path) as f:
            for line in f:
                if line.strip().startswith("pip_mirror:"):
                    val = line.split(":", 1)[1].strip().strip("\"'")
                    if val and val.lower() not in ("null", "none", ""):
                        return val
    except OSError:
        pass
    return None


def _install_deps(missing: list[str]):
    """Install missing packages using the venv's pip.

    Uses the pip mirror from config.yaml if set, otherwise defaults
    to the official PyPI index (no -i flag).
    """
    pip_cmd = [_venv_python(), "-m", "pip", "install", "--quiet"]
    mirror = _load_pip_mirror()
    if mirror:
        pip_cmd += ["-i", mirror]
    pip_cmd += missing

    result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print("[paper-fetcher] pip install failed:")
        print(result.stderr)
        sys.exit(1)


def _check_dependency(import_name: str) -> bool:
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def _missing_deps() -> list[str]:
    return [pkg for pkg in _REQUIRED_IMPORTS if not _check_dependency(_REQUIRED_IMPORTS[pkg])]


def _bootstrap():
    """Ensure we are running inside the project venv with all deps installed."""
    # ── Step 1: re-exec into .venv if not already inside it ────────────────
    if not _in_project_venv():
        _ensure_venv()
        # Re-exec this script using the venv's interpreter
        venv_py = _venv_python()
        if not os.path.isfile(venv_py):
            print(f"[paper-fetcher] Venv python not found at {venv_py}")
            sys.exit(1)
        os.execv(venv_py, [venv_py] + sys.argv)

    # ── Step 2: install any missing packages ───────────────────────────────
    missing = _missing_deps()
    if not missing:
        return

    print(f"[paper-fetcher] Installing missing dependencies: {', '.join(missing)}")
    _install_deps(missing)

    still_missing = _missing_deps()
    if still_missing:
        print(f"[paper-fetcher] Some packages still missing: {', '.join(still_missing)}")
        sys.exit(1)

    print("[paper-fetcher] Dependencies installed. Running your request...")


# ---------------------------------------------------------------------------
# Intent detection & CLI dispatch
# ---------------------------------------------------------------------------

SEARCH_MARKERS = ["search", "find", "look for", "查找", "搜索", "搜", "找", "查"]
DOWNLOAD_MARKERS = ["download", "sci-hub", "scihub", "get the pdf", "pull", "下载", "下", "获取"]
LIST_MARKERS = ["list", "show", "saved", "已保存", "列出", "显示", "topics"]


def detect_intent(message: str) -> tuple[str, str | None]:
    msg = message.lower().strip()
    for m in DOWNLOAD_MARKERS:
        if m in msg:
            return ("download", _extract_topic(msg, m))
    for m in LIST_MARKERS:
        if m in msg:
            return ("list", None)
    for m in SEARCH_MARKERS:
        if m in msg:
            return ("search", _extract_topic(msg, m))
    return ("search", _extract_topic(msg, None))


def _extract_topic(msg: str, marker: str | None) -> str | None:
    if marker:
        idx = msg.find(marker)
        msg = msg[idx + len(marker):]
    for filler in [
        "papers on", "papers about", "paper on", "paper about",
        "for", "on", "about", "from", "the", "my", "论文", "相关",
    ]:
        msg = re.sub(rf"\b{re.escape(filler)}\b", "", msg, flags=re.IGNORECASE)
    msg = msg.strip().strip("'\"").strip()
    return msg if len(msg) > 2 else None


def run_cli(action: str, topic: str | None, extra_args: list[str] | None = None):
    cmd = [sys.executable, "-m", "cli.main", action]
    if topic:
        cmd += ["--topic", topic]
    if extra_args:
        cmd += extra_args
    # Skill invocations are non-TTY, so pass --all for download to skip interactive selection
    if action == "download":
        cmd.append("--all")
    subprocess.run(cmd, cwd=PROJECT_ROOT)


def main():
    # Check for help flag first
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h", "help"]:
            print("paper-fetcher: Search academic papers and download from Sci-Hub")
            print()

            print("Usage:")
            print("  python skill.py [command] [topic]")
            print()

            print("Commands:")
            print("  search [topic]    Search for papers on a topic")
            print("  download [topic]  Download papers from saved results")
            print("  list             List saved topics")
            print("  help             Show this help message")
            print()

            print("Examples:")
            print("  python skill.py search machine learning")
            print("  python skill.py download deep learning")
            print("  python skill.py list")
            print()

            print("You can also use natural language:")
            print("  python skill.py find papers about AI")
            print("  python skill.py scihub papers on quantum computing")
            print("  python skill.py 下载关于人工智能的论文")
            sys.exit(0)

    # Auto-create venv and install dependencies on first run
    _bootstrap()

    # Get user input from command line or stdin
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = sys.stdin.read().strip()

    if not user_input:
        print("paper-fetcher: Search academic papers and download from Sci-Hub")
        print("  Try: search papers on federated learning")
        print("  Or use CLI: papers search --topic \"federated learning\"")
        print("  Run 'python skill.py help' for more information")
        sys.exit(0)

    action, topic = detect_intent(user_input)

    if topic:
        print(f"[paper-fetcher] {action}: {topic}")
        run_cli(action, topic)
    else:
        print(f"[paper-fetcher] Running: papers {action}")
        run_cli(action, None)


if __name__ == "__main__":
    main()
