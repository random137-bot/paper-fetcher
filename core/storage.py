import json
import re
from datetime import date as dt_date
from datetime import datetime
from pathlib import Path
from core.models import Paper, TopicInfo
from core.utils import slugify


def load_index(base_dir: Path) -> dict[str, TopicInfo]:
    index_path = base_dir / ".index.json"
    if not index_path.exists():
        return {}
    with open(index_path) as f:
        data = json.load(f)

    cleaned = {}
    for k, v in data.items():
        topic_dir = base_dir / v.get("path", k)
        if topic_dir.exists():
            cleaned[k] = TopicInfo(**v)

    # Auto-clean stale entries whose directories were deleted
    if len(cleaned) < len(data):
        save_index(base_dir, cleaned)

    return cleaned


def save_index(base_dir: Path, index: dict[str, TopicInfo]):
    base_dir.mkdir(parents=True, exist_ok=True)
    serialized = {
        k: {
            "path": v.path,
            "keywords": v.keywords,
            "paper_count": v.paper_count,
            "last_updated": v.last_updated,
        }
        for k, v in index.items()
    }
    with open(base_dir / ".index.json", "w") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)


def _escape_md(text: str) -> str:
    """Escape special markdown table characters (|) and normalize whitespace."""
    return text.replace("|", "/").replace("\n", " ") if text else ""


def save_results(topic_dir: Path, topic_name: str, papers: list[Paper], sources: list[str]):
    topic_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Search Results: {topic_name}", ""]
    lines.append("| # | Title | Authors | Date | DOI | Citations | Abstract |")
    lines.append("|---|-------|---------|------|-----|-----------|----------|")
    for i, p in enumerate(papers, 1):
        if len(p.authors) > 3:
            author_str = ", ".join(p.authors[:3]) + " et al."
        else:
            author_str = ", ".join(p.authors) if p.authors else "N/A"
        date_str = p.date.isoformat() if p.date else "N/A"
        doi = p.doi or "N/A"
        citations = str(p.citations) if p.citations is not None else "N/A"
        abstract = (p.abstract[:80] + "...") if len(p.abstract) > 80 else (p.abstract or "")
        lines.append(f"| {i} | {_escape_md(p.title)} | {_escape_md(author_str)} | {date_str} | {_escape_md(doi)} | {citations} | {_escape_md(abstract)} |")
    lines.append("")
    lines.append(f"_Searched: {datetime.now().strftime('%Y-%m-%d')} | Sources: {', '.join(sources)}_")
    with open(topic_dir / "results.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    # Also save full metadata as JSON for reliable round-trip parsing
    _save_papers_json(topic_dir, papers)


def _save_papers_json(topic_dir: Path, papers: list[Paper]):
    """Save full paper metadata (including abstract, URLs) as JSON."""
    serialized = []
    for p in papers:
        serialized.append({
            "title": p.title,
            "authors": p.authors,
            "date": p.date.isoformat() if p.date else None,
            "doi": p.doi,
            "citations": p.citations,
            "source": p.source,
            "url": p.url,
            "abstract": p.abstract,
            "pub_url": p.pub_url,
            "eprint_url": p.eprint_url,
        })
    with open(topic_dir / "papers.json", "w") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)


def parse_results(topic_dir: Path) -> list[Paper]:
    # Prefer the JSON file (has full metadata including abstract, URLs)
    json_path = topic_dir / "papers.json"
    if json_path.exists():
        with open(json_path) as f:
            data = json.load(f)
        papers = []
        for d in data:
            pdate = None
            if d.get("date"):
                try:
                    pdate = dt_date.fromisoformat(d["date"])
                except (ValueError, TypeError):
                    pass
            papers.append(Paper(
                title=d["title"],
                authors=d.get("authors", []),
                date=pdate,
                doi=d.get("doi"),
                citations=d.get("citations"),
                source=d.get("source", ""),
                url=d.get("url", ""),
                abstract=d.get("abstract", ""),
                pub_url=d.get("pub_url", ""),
                eprint_url=d.get("eprint_url", ""),
            ))
        return papers

    # Fallback: parse results.md (6 or 7 column format)
    results_path = topic_dir / "results.md"
    if not results_path.exists():
        return []
    papers = []
    with open(results_path) as f:
        content = f.read()
    for line in content.split("\n"):
        line = line.strip()
        if not line.startswith("| ") or line.startswith("| #") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 6:
            continue
        title = parts[1]
        author_str = parts[2]
        authors = [a.strip() for a in author_str.replace(" et al.", "").split(",")] if author_str != "N/A" else []
        date_str = parts[3]
        doi = parts[4] if parts[4] != "N/A" else None
        citations = int(parts[5]) if parts[5] != "N/A" else None
        abstract = parts[6] if len(parts) >= 7 else ""
        pdate = None
        if date_str != "N/A":
            try:
                pdate = dt_date.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass
        papers.append(Paper(title=title, authors=authors, date=pdate, doi=doi,
                            citations=citations, abstract=abstract))
    return papers


def log_error(base_dir: Path, message: str):
    base_dir.mkdir(parents=True, exist_ok=True)
    log_path = base_dir / ".errors.log"
    # Keep last ~500 KB to avoid unbounded growth
    if log_path.exists() and log_path.stat().st_size > 500 * 1024:
        log_path.rename(base_dir / ".errors.log.old")
    with open(log_path, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")


def existing_files(topic_dir: Path) -> set[str]:
    """
    Return set of file identifiers for already-downloaded PDFs.

    Each PDF contributes TWO possible matches so that both the old naming
    (no DOI suffix) and the new naming (with `[DOI]` or `[arXiv:...]` bracket)
    are recognized:
      - The full stem (e.g. ``2017-02-19 Some Title [10.xxxx_yyyy]``)
      - The title-only stem stripped of any ``[bracket]`` suffix
        (e.g. ``2017-02-19 Some Title``)
    """
    if not topic_dir.exists():
        return set()
    stems: set[str] = set()
    for p in topic_dir.glob("*.pdf"):
        stems.add(p.stem)
        # Also match the stem without DOI/arXiv bracket for backward compat
        bare = re.sub(r"\s*\[[^\]]*\]\s*$", "", p.stem).strip()
        if bare and bare != p.stem:
            stems.add(bare)
    return stems
