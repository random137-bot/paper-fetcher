from datetime import date
from unittest.mock import patch, MagicMock
from core.models import Paper
from core.searcher import deduplicate, normalize_title, _enrich_dois, _lookup_doi_crossref


def test_normalize_title():
    assert normalize_title("Hello   World") == "hello world"
    assert normalize_title("  Test Paper.  ") == "test paper"
    assert normalize_title("Paper Title.") == "paper title"


def test_deduplicate_by_doi():
    p1 = Paper(title="A", doi="10.0/x", citations=100, source="semantic")
    p2 = Paper(title="A (different casing)", doi="10.0/X", citations=50, source="arxiv")
    result = deduplicate([p1, p2])
    assert len(result) == 1
    assert result[0].citations == 100


def test_deduplicate_by_title():
    p1 = Paper(title="Communication Efficient Learning", authors=["McMahan"], date=date(2017, 1, 1), source="semantic")
    p2 = Paper(title="Communication-Efficient Learning", authors=["McMahan"], source="arxiv")
    result = deduplicate([p1, p2])
    assert len(result) == 1
    assert result[0].date is not None


def test_deduplicate_cross_key():
    """Papers with same title but one has DOI, the other doesn't -- must merge."""
    p1 = Paper(title="Deep Learning Paper", authors=["LeCun, Y."], doi="10.1038/nature14539", citations=100000, source="semantic")
    p2 = Paper(title="Deep learning paper", authors=["LeCun Y"], citations=50000, source="scholar")
    result = deduplicate([p1, p2])
    assert len(result) == 1, "Cross-key dedup failed: DOI paper and title-only paper not merged"
    assert result[0].doi == "10.1038/nature14539", "Should keep the paper with DOI"
    assert result[0].citations == 100000, "Should keep higher citations"


def test_deduplicate_keeps_distinct():
    p1 = Paper(title="Paper A", source="semantic")
    p2 = Paper(title="Paper B", source="arxiv")
    p3 = Paper(title="Paper C", source="scholar")
    result = deduplicate([p1, p2, p3])
    assert len(result) == 3


def test_deduplicate_multiple_in_group():
    """3 copies of same paper from 3 sources → 1 result with best data."""
    p1 = Paper(title="Same Paper", authors=["Smith"], doi="10.0/x", citations=10, date=date(2024, 1, 1), source="semantic")
    p2 = Paper(title="Same Paper", authors=["Smith"], source="arxiv")
    p3 = Paper(title="Same Paper", authors=["Smith"], citations=5, source="scholar")
    result = deduplicate([p1, p2, p3])
    assert len(result) == 1
    assert result[0].doi == "10.0/x"
    assert result[0].date == date(2024, 1, 1)


def test_search_no_sources():
    from core.searcher import search
    result = search("test", sources=[], max_results=10)
    assert result == []


def test_enrich_dois_preserves_existing():
    p = Paper(title="Test", doi="10.0/existing")
    result = _enrich_dois([p])
    assert result[0].doi == "10.0/existing"


@patch("core.searcher.requests.get")
def test_enrich_dois_lookup_adds_doi(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "items": [{"DOI": "10.1234/new", "title": ["Missing DOI Paper"]}]
        }
    }
    mock_get.return_value = mock_resp

    p = Paper(title="Missing DOI Paper", authors=["Bengio, Y."])
    result = _enrich_dois([p])
    assert result[0].doi == "10.1234/new"
    # Title and other fields preserved
    assert result[0].title == "Missing DOI Paper"


@patch("core.searcher.requests.get")
def test_enrich_dois_lookup_not_found(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"items": []}}
    mock_get.return_value = mock_resp

    p = Paper(title="Obscure Unknown Paper")
    result = _enrich_dois([p])
    assert result[0].doi is None


def test_lookup_doi_crossref_builds_query():
    doi = _lookup_doi_crossref("Deep Residual Learning for Image Recognition", "he")
    assert doi is not None
    assert not doi.startswith("10.65215")
