from pathlib import Path
from core.config import load_config
from core.storage import parse_results, existing_files, slugify, log_error, load_index
from core.downloader import download, build_filename
from core.proxy import ProxyManager


def _resolve_topic_dir(base_dir: Path, topic_input: str) -> Path | None:
    """Resolve a topic input to an existing topic directory.

    Tries (in order):
      1. slugify(topic_input) — works when user passes the original search query
      2. topic_input as raw directory name — works when user passes the slug verbatim
      3. Match against index paths — partial/prefix fallback
    """
    # Strategy 1: slugified form
    slug = slugify(topic_input)
    candidate = base_dir / slug
    if (candidate / "results.md").exists():
        return candidate

    # Strategy 2: raw input as directory name
    candidate = base_dir / topic_input
    if (candidate / "results.md").exists():
        return candidate

    # Strategy 3: match against index paths (handles truncated slugs)
    index = load_index(base_dir)
    for info in index.values():
        candidate = base_dir / info.path
        if not (candidate / "results.md").exists():
            continue
        if info.path == slug or info.path == topic_input:
            return candidate
        # One is a prefix/substring of the other
        if info.path.startswith(topic_input) or topic_input.startswith(info.path):
            return candidate

    return None


def run(args):
    config = load_config()
    proxy_mgr = ProxyManager(config)
    base_dir = Path(config["storage"]["base_dir"])

    topic_dir = _resolve_topic_dir(base_dir, args.topic)
    if topic_dir is None:
        print(f"No results.md found for topic '{args.topic}'.")
        if base_dir.exists():
            topics = [d.name for d in base_dir.iterdir() if d.is_dir() and (d / "results.md").exists()]
            if topics:
                print(f"Available topics: {', '.join(topics)}")
        return

    papers = parse_results(topic_dir)
    if not papers:
        print("No papers found in results.md.")
        return

    print(f"Found {len(papers)} papers in '{args.topic}'.")

    # Filter already downloaded
    existing = existing_files(topic_dir)
    pending = [p for p in papers if build_filename(p).removesuffix(".pdf") not in existing]

    if not pending:
        print("All papers already downloaded.")
        return

    print(f"{len(pending)} papers pending ({len(papers) - len(pending)} already downloaded).")

    # Selection
    if getattr(args, "all", False):
        selected = pending
    else:
        try:
            import questionary
            choices = [
                questionary.Choice(
                    title=f"  [{i+1}] {p.title[:100]} ({p.date or 'no date'}) -- {p.doi or 'no DOI'}",
                    value=i,
                )
                for i, p in enumerate(pending)
            ]
            indices = questionary.checkbox("Select papers to download:", choices=choices).ask()
            if indices is None or len(indices) == 0:
                print("No papers selected.")
                return
            selected = [pending[i] for i in indices]
        except (ImportError, OSError):
            print("Interactive selection unavailable (no TTY or questionary missing). Use --all to download all pending.")
            return

    # Download
    domains = config["download"]["scihub_domains"]
    timeout = config["download"]["timeout"]

    success = 0
    for i, paper in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] Downloading: {paper.title[:80]}...")
        result = download(paper, topic_dir, domains=domains, timeout=timeout,
                          proxy_manager=proxy_mgr)
        if result:
            print(f"  -> Saved: {result.name}")
            success += 1
        else:
            print(f"  -> Failed.")
            log_error(base_dir, f"Download failed: {paper.title} ({paper.doi or 'no DOI'})")

    print(f"\nDone. {success}/{len(selected)} downloaded successfully.")
