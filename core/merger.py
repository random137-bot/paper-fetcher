import re
from rapidfuzz import fuzz
from core.utils import slugify


def build_keywords(topic: str) -> set[str]:
    words = re.findall(r"\w+", topic.lower())
    return {w for w in words if len(w) > 2}


def find_similar_topic(
    topic: str,
    existing_index: dict,
    threshold: int = 85,
    keyword_overlap: float = 0.6,
) -> str | None:
    slug = slugify(topic)
    if not existing_index:
        return None

    # 1. Exact slug match
    if slug in existing_index:
        return slug

    keywords = build_keywords(topic)

    for existing_slug, info in existing_index.items():
        # 2. Fuzzy ratio on slug
        if fuzz.ratio(slug, existing_slug) >= threshold:
            return existing_slug

        # 3. Keyword overlap
        existing_kw = set(info.get("keywords", []))
        if keywords and existing_kw:
            shared = keywords & existing_kw
            if len(shared) / min(len(keywords), len(existing_kw)) >= keyword_overlap:
                return existing_slug

    return None
