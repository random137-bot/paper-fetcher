import hashlib
import re

# Max length for topic directory slugs. Longer slugs are truncated and
# appended with a short hash to keep them unique yet filesystem-friendly.
MAX_SLUG_LENGTH = 50


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[/\\]", " ", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    # Truncate long slugs, keeping a short hash for uniqueness
    if len(text) > MAX_SLUG_LENGTH:
        suffix = hashlib.md5(text.encode()).hexdigest()[:6]
        text = text[:MAX_SLUG_LENGTH].rstrip("-") + "-" + suffix
    return text
