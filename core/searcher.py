import functools
import logging
import re
import time
import urllib.parse
import requests
from core.models import Paper
from core.sources.arxiv import ArxivSource
from core.sources.semantic import SemanticSource

logger = logging.getLogger(__name__)

SOURCE_CLASSES = {
    "arxiv": ArxivSource,
    "semantic": SemanticSource,
}


def normalize_title(title: str) -> str:
    title = title.lower().strip().rstrip(".")
    title = re.sub(r"[-\u2013\u2014]", " ", title)
    return re.sub(r"\s+", " ", title)


def _author_last_name(authors: list[str]) -> str:
    """Extract last name of first author for matching."""
    if not authors:
        return ""
    return authors[0].lower().split()[-1].strip(".")


def _is_duplicate(a: Paper, b: Paper) -> bool:
    """Check if two papers are the same by DOI or title+author."""
    # DOI match (both have DOIs)
    if a.doi and b.doi:
        if a.doi.lower().strip() == b.doi.lower().strip():
            return True
    # Title + first author match
    if normalize_title(a.title) == normalize_title(b.title):
        a_first = _author_last_name(a.authors)
        b_first = _author_last_name(b.authors)
        if a_first and b_first and a_first == b_first:
            return True
    return False


def deduplicate(papers: list[Paper]) -> list[Paper]:
    """Group equivalent papers and keep the best from each group."""
    if not papers:
        return []

    groups: list[list[Paper]] = []

    for p in papers:
        matched_group = None
        for group in groups:
            if _is_duplicate(p, group[0]):
                matched_group = group
                break

        if matched_group is not None:
            matched_group.append(p)
        else:
            groups.append([p])

    return [_best_in_group(g) for g in groups]


def _paper_score(p: Paper) -> int:
    return (1 if p.doi else 0) + (1 if p.citations else 0) + (1 if p.date else 0)


def _best_in_group(group: list[Paper]) -> Paper:
    return max(group, key=_paper_score)


def _enrich_dois(papers: list[Paper]) -> list[Paper]:
    """For papers missing DOIs, try to look them up via Crossref API."""
    enriched = []
    for idx, p in enumerate(papers):
        if p.doi or not p.title:
            enriched.append(p)
            continue

        # Rate limit: Crossref polite pool recommends 1 req/s
        if idx > 0:
            time.sleep(1.0)

        doi = _lookup_doi_crossref(p.title, _author_last_name(p.authors))
        if doi:
            enriched.append(Paper(
                title=p.title,
                authors=p.authors,
                date=p.date,
                doi=doi,
                citations=p.citations,
                source=p.source,
                url=p.url,
                abstract=p.abstract,
                pub_url=p.pub_url,
                eprint_url=p.eprint_url,
            ))
        else:
            enriched.append(p)

    return enriched


def _title_similarity(a: str, b: str) -> float:
    """Token overlap ratio between two normalized titles (0.0 – 1.0)."""
    a_tokens = set(normalize_title(a).split())
    b_tokens = set(normalize_title(b).split())
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = a_tokens & b_tokens
    return len(intersection) / max(len(a_tokens), len(b_tokens))


@functools.lru_cache(maxsize=256)
def _lookup_doi_crossref(title: str, first_author_last: str = "") -> str | None:
    """Look up a paper's DOI via Crossref API by title and author.

    Cached to avoid repeated lookups for the same title across sources
    (pattern: use functools.lru_cache like a memoised lookup table).

    Uses query.title for targeted search and validates the returned title
    via title similarity + optional author check to reject fuzzy mismatches.
    """
    MIN_SIMILARITY = 0.75
    # Reserved/test DOI prefixes that should not be used
    BLOCKED_PREFIXES = ("10.65215",)
    try:
        q = title.strip().rstrip(".")
        url = (
            f"https://api.crossref.org/works"
            f"?query.title={urllib.parse.quote(q)}"
            f"&rows=5"
        )
        if first_author_last:
            url += f"&query.author={urllib.parse.quote(first_author_last)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("message", {}).get("items", [])
            best_match = None
            best_score = 0.0
            for item in items:
                doi = item.get("DOI") or ""
                # Skip reserved/test DOI prefixes
                if doi.startswith(BLOCKED_PREFIXES):
                    continue
                ret_title = (item.get("title") or [""])[0]
                score = _title_similarity(title, ret_title)
                # Author bonus: +0.1 if first author last name matches
                if first_author_last and score < 1.0:
                    authors = item.get("author") or []
                    if any(
                        (a.get("family") or "").lower() == first_author_last
                        for a in authors
                    ):
                        score += 0.1
                if score > best_score:
                    best_score = score
                    best_match = doi
            if best_match and best_score >= MIN_SIMILARITY:
                return best_match
            else:
                logger.debug(
                    "Crossref: no close match for '%s' (best=%.2f)",
                    title, best_score,
                )
    except requests.exceptions.RequestException as exc:
        logger.debug("Crossref lookup failed for '%s': %s", title, exc)
    except Exception as exc:
        logger.debug("Crossref lookup error for '%s': %s", title, exc)
    return None


def search(topic: str, sources: list[str] | None = None, max_results: int = 20) -> list[Paper]:
    if sources is None:
        sources = ["semantic", "arxiv"]

    all_papers: list[Paper] = []
    source_stats: dict[str, int] = {}
    from core.config import load_config
    config = load_config()

    for src_name in sources:
        cls = SOURCE_CLASSES.get(src_name)
        if cls is None:
            logger.warning("Unknown source '%s', skipping", src_name)
            continue
        t0 = time.monotonic()
        try:
            kwargs = {}
            if src_name == "semantic":
                kwargs["api_key"] = (
                    config.get("sources", {})
                    .get("semantic", {})
                    .get("api_key")
                )
            instance = cls(**kwargs)
            papers = instance.search(topic, max_results=max_results)
            elapsed = time.monotonic() - t0
            source_stats[src_name] = len(papers)
            logger.info("Source '%s' returned %d papers in %.1fs", src_name, len(papers), elapsed)
            all_papers.extend(papers)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.warning("Source '%s' failed after %.1fs: %s", src_name, elapsed, exc)
            source_stats[src_name] = 0
            continue

    logger.info("Search stats: %s", source_stats)
    deduped = deduplicate(all_papers)
    deduped = _enrich_dois(deduped)
    deduped.sort(key=lambda p: p.citations or 0, reverse=True)
    return deduped[:max_results]
