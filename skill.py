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
BOOTSTRAP_SENTINEL = os.path.join(VENV_DIR, ".deps-installed")

# CWD when the skill was launched (e.g. where Claude Code was started).
# Used to save papers relative to the user's working directory rather than
# the skill's installation path when invoked by an agent.
_LAUNCH_CWD = os.environ.get("PAPER_FETCHER_CWD") or os.getcwd()

# ---------------------------------------------------------------------------
# Bootstrap: ensure required packages are installed inside a project-local
# virtual environment (venv), avoiding any dependency on conda or global pip.
# ---------------------------------------------------------------------------

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


def _in_project_venv() -> bool:
    """Return True if already running inside the project's .venv.

    Uses sys.prefix rather than comparing os.path.realpath on the binaries.
    python3 -m venv creates .venv/bin/python as a symlink back to the original
    Python, so realpath resolves both to the same file -- a false positive.
    sys.prefix inside a venv points to the venv directory itself, which is
    unambiguous.
    """
    return os.path.realpath(sys.prefix) == os.path.realpath(VENV_DIR)


def _venv_python() -> str:
    """Path to the python binary inside the project venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _ensure_venv():
    """Create or validate the project venv.

    Re-creates the venv if the directory exists but the python binary is missing
    (e.g. a previous venv creation was interrupted).
    """
    venv_py = _venv_python()
    if os.path.isdir(VENV_DIR) and os.path.isfile(venv_py):
        return

    if os.path.isdir(VENV_DIR):
        print(f"[paper-fetcher] Venv directory exists but python binary missing, re-creating ...")
        import shutil
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    print(f"[paper-fetcher] Creating virtual environment at {VENV_DIR} ...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", VENV_DIR],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print("[paper-fetcher] Failed to create venv:", result.stderr)
        sys.exit(1)


def _ensure_config():
    """Auto-create config.yaml from config.example.yaml on first run."""
    config = os.path.join(PROJECT_ROOT, "config.yaml")
    example = os.path.join(PROJECT_ROOT, "config.example.yaml")
    if not os.path.exists(config) and os.path.exists(example):
        import shutil
        shutil.copy2(example, config)
        print("[paper-fetcher] Created config.yaml from config.example.yaml — edit it to customize settings.")


def _write_sentinel():
    """Create the sentinel file so future runs skip the dep check entirely."""
    os.makedirs(VENV_DIR, exist_ok=True)
    with open(BOOTSTRAP_SENTINEL, "w") as f:
        f.write("ok\n")


def _load_pip_mirror() -> str | None:
    """Read pip mirror from config.yaml (if set) without requiring yaml dep."""
    _ensure_config()
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

    try:
        result = subprocess.run(pip_cmd, timeout=120)
    except subprocess.TimeoutExpired:
        print("[paper-fetcher] pip install timed out after 120 s")
        if not mirror:
            print("[paper-fetcher] Tip: set 'pip_mirror' in config.yaml to use a faster PyPI mirror")
            print("[paper-fetcher]   e.g. pip_mirror: https://pypi.tuna.tsinghua.edu.cn/simple")
        else:
            print(f"[paper-fetcher] Current mirror: {mirror} -- try a different one or check your network")
        sys.exit(1)
    if result.returncode != 0:
        print("[paper-fetcher] pip install failed (see output above)")
        if not mirror:
            print("[paper-fetcher] Tip: set 'pip_mirror' in config.yaml to use a faster PyPI mirror")
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

    # ── Fast path: sentinel file present means deps are already installed ──
    if os.path.isfile(BOOTSTRAP_SENTINEL):
        return

    # ── Step 2: install any missing packages ───────────────────────────────
    missing = _missing_deps()
    if not missing:
        _write_sentinel()
        return

    print(f"[paper-fetcher] Installing missing dependencies: {', '.join(missing)}")
    _install_deps(missing)

    still_missing = _missing_deps()
    if still_missing:
        print(f"[paper-fetcher] Some packages still missing: {', '.join(still_missing)}")
        sys.exit(1)

    print("[paper-fetcher] Dependencies installed. Running your request...")
    _write_sentinel()


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
    env = os.environ.copy()
    env["PAPER_FETCHER_CWD"] = _LAUNCH_CWD
    try:
        subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, timeout=120)
    except subprocess.TimeoutExpired:
        print(f"[paper-fetcher] Timeout: {action} did not complete within 120 s")
        print("[paper-fetcher] Tip: Google Scholar is often rate-limited. Try '--sources semantic,arxiv'")


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
        args = sys.argv[1:]

        # Detect CLI-style invocation with flags like --topic / --merge-into.
        # These are passed through as extra_args to the CLI subprocess so the
        # agent can use natural-language and CLI-style commands interchangeably.
        if len(args) >= 2 and args[0] in ("search", "download", "list") and args[1].startswith("--"):
            action = args[0]
            extra_args = args[1:]
            print(f"[paper-fetcher] {action}: {extra_args}")
            run_cli(action, None, extra_args)
            return

        user_input = " ".join(args)
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
