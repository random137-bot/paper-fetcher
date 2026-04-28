from pathlib import Path
from datetime import datetime
from core.config import load_config
from core.searcher import search as core_search
from core.storage import save_results, slugify, load_index, save_index, parse_results
from core.proxy import ProxyManager
from core.merger import find_similar_topic, build_keywords
from core.models import TopicInfo


def run(args):
    config = load_config()
    proxy_mgr = ProxyManager(config)
    base_dir = Path(config["storage"]["base_dir"])

    sources = args.sources.split(",") if args.sources else ["semantic", "arxiv", "scholar"]

    # ── Step 1: determine target topic slug ────────────────────────────────
    index = load_index(base_dir)

    # Priority: --merge-into > auto-detect > slugify(topic)
    merge_into = getattr(args, "merge_into", None)  # explicit LLM-guided merge
    if merge_into and merge_into in index:
        slug = merge_into
        topic_dir = base_dir / slug
        print(f"Merging into explicit topic '{slug}'.")
    elif not getattr(args, "new_topic", False):
        slug = slugify(args.topic)
        topic_dir = base_dir / slug
        existing_for_check = {k: {"keywords": v.keywords} for k, v in index.items()}
        similar = find_similar_topic(args.topic, existing_for_check)
        if similar and similar != slug:
            print(f"Merging with existing topic '{similar}' (--merge-into for explicit).")
            slug = similar
            topic_dir = base_dir / slug
    else:
        slug = slugify(args.topic)
        topic_dir = base_dir / slug

    # ── Step 2: search ─────────────────────────────────────────────────────
    print(f"Searching for '{args.topic}' across {', '.join(sources)}...")
    new_papers = core_search(args.topic, sources=sources, max_results=args.max,
                             proxy_manager=proxy_mgr)
    print(f"Found {len(new_papers)} unique results after deduplication.")

    if not new_papers:
        print("No results found.")
        return

    # ── Step 3: merge with existing papers (if topic already has results) ──
    from core.searcher import deduplicate
    existing_papers = parse_results(topic_dir) if topic_dir.exists() else []
    if existing_papers:
        combined = deduplicate(existing_papers + new_papers)
        added = len(combined) - len(existing_papers)
        print(f"Merged with {len(existing_papers)} existing papers → {len(combined)} total (+{added} new).")
        papers = combined
    else:
        papers = new_papers

    # ── Step 4: save ──────────────────────────────────────────────────────
    save_results(topic_dir, args.topic, papers, sources)
    index[slug] = TopicInfo(
        path=slug,
        keywords=list(build_keywords(args.topic)),
        paper_count=len(papers),
        last_updated=datetime.now().isoformat(),
    )
    save_index(base_dir, index)

    print(f"Results saved to {topic_dir / 'results.md'}")
    _print_table(papers)


def _print_table(papers):
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p.authors[:2])
        if len(p.authors) > 2:
            authors += " et al."
        doi = p.doi or "-"
        citations = str(p.citations) if p.citations is not None else "-"
        abstract = (p.abstract[:80] + "...") if len(p.abstract) > 80 else (p.abstract or "")
        abstract = abstract.replace("\n", " ")
        print(f"  {i}. {p.title[:80]}")
        print(f"     {authors} | {p.date} | doi:{doi} | cited:{citations}")
        if abstract:
            print(f"     {abstract}")
        if p.eprint_url:
            print(f"     arXiv: {p.eprint_url}")
        elif p.pub_url:
            print(f"     URL: {p.pub_url}")
        print()
