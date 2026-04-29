from datetime import date
from unittest.mock import patch, MagicMock
from core.sources.arxiv import ArxivSource
from core.sources.semantic import SemanticSource
from core.sources.scholar import ScholarSource


# --- arXiv tests ---

def fake_arxiv_result(title, authors, published, doi=None):
    r = MagicMock()
    r.title = title
    r.authors = [MagicMock(name=a) for a in authors]
    for i, a in enumerate(authors):
        r.authors[i].name = a
    r.published = published
    r.doi = doi
    r.entry_id = f"http://arxiv.org/abs/{title.replace(' ', '')}"
    return r


@patch("core.sources.arxiv.arxiv.Search")
@patch("core.sources.arxiv.arxiv.Client")
def test_arxiv_search_returns_papers(mock_client, mock_search):
    from datetime import datetime as dt
    mock_client.return_value = MagicMock()
    mock_search.return_value = MagicMock()
    mock_search.return_value.max_results = 5
    mock_search.return_value.sort_by = MagicMock()
    r1 = fake_arxiv_result("Paper One", ["Alice", "Bob"], dt(2024, 1, 15), "10.0/one")
    r2 = fake_arxiv_result("Paper Two", ["Charlie"], dt(2023, 6, 1))
    mock_client.return_value.results.return_value = [r1, r2]

    source = ArxivSource(delay_min=0, delay_max=0)
    papers = source.search("test topic", max_results=5)

    assert len(papers) == 2
    assert papers[0].title == "Paper One"
    assert papers[0].authors == ["Alice", "Bob"]
    assert papers[0].date == date(2024, 1, 15)
    assert papers[0].doi == "10.0/one"
    assert papers[0].source == "arxiv"
    assert papers[1].doi is None


@patch("core.sources.arxiv.arxiv.Search")
@patch("core.sources.arxiv.arxiv.Client")
def test_arxiv_search_empty(mock_client, mock_search):
    mock_client.return_value = MagicMock()
    mock_client.return_value.results.return_value = []
    source = ArxivSource(delay_min=0, delay_max=0)
    papers = source.search("nonexistent", max_results=5)
    assert papers == []


@patch("core.sources.arxiv.arxiv.Search")
@patch("core.sources.arxiv.arxiv.Client")
def test_arxiv_search_error_graceful(mock_client, mock_search):
    mock_client.side_effect = Exception("API down")
    source = ArxivSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=5)
    assert papers == []


# --- Semantic Scholar tests (SDK) ---

from semanticscholar.Paper import Paper as S2Paper
from semanticscholar.Author import Author as S2Author


def _fake_s2_paper(title="Test Paper", authors=None, year=2024,
                   doi=None, arxiv_id=None, citation_count=0,
                   paper_id="abc123", url=None, abstract=""):
    """Build a fake semanticscholar.Paper object."""
    p = MagicMock(spec=S2Paper)
    p.title = title
    p.authors = [S2Author({"authorId": "1", "name": a}) for a in authors] if authors else None
    p.year = year
    p.externalIds = {}
    if doi:
        p.externalIds["DOI"] = doi
    if arxiv_id:
        p.externalIds["ArXiv"] = arxiv_id
    p.citationCount = citation_count
    p.paperId = paper_id
    p.url = url or f"https://api.semanticscholar.org/paper/{paper_id}"
    p.abstract = abstract
    return p


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_returns_papers(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(
            title="Deep Learning Review",
            authors=["Yann LeCun", "Yoshua Bengio"],
            year=2015,
            doi="10.1038/nature14539",
            citation_count=50000,
        )
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("deep learning", max_results=10)

    assert len(papers) == 1
    assert papers[0].title == "Deep Learning Review"
    assert papers[0].authors == ["Yann LeCun", "Yoshua Bengio"]
    assert papers[0].citations == 50000
    assert papers[0].doi == "10.1038/nature14539"
    assert papers[0].source == "semantic"
    mock_client.search_paper.assert_called_once_with(
        "deep learning",
        limit=10,
        fields=["title", "authors", "year", "externalIds", "citationCount", "url", "abstract"],
    )


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_missing_fields(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(title="Unknown Paper", authors=None, year=None,
                       doi=None, citation_count=None, abstract=None, url=None)
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)

    assert len(papers) == 1
    assert papers[0].title == "Unknown Paper"
    assert papers[0].authors == []
    assert papers[0].doi is None
    assert papers[0].date is None
    assert papers[0].citations is None


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_with_arxiv_id(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = [
        _fake_s2_paper(
            title="ArXiv Paper",
            authors=["Jones, K."],
            year=2023,
            arxiv_id="2301.12345",
        )
    ]
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)

    assert len(papers) == 1
    assert papers[0].eprint_url == "https://arxiv.org/abs/2301.12345"


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = []
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("nonexistent", max_results=10)
    assert papers == []


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.side_effect = Exception("API error")
    mock_client_cls.return_value = mock_client

    source = SemanticSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=10)
    assert papers == []


@patch("core.sources.semantic.SemanticScholar")
def test_semantic_search_with_api_key(mock_client_cls):
    mock_client = MagicMock()
    mock_client.search_paper.return_value = []
    mock_client_cls.return_value = mock_client

    source = SemanticSource(api_key="test-key-123", delay_min=0, delay_max=0)
    source.search("test", max_results=10)

    mock_client_cls.assert_called_once_with(api_key="test-key-123")


# --- Scholar tests ---

def _fake_scholarly_pub(title, authors, year, doi=None, citations=0):
    pub = {
        "bib": {
            "title": title,
            "author": authors,
            "pub_year": str(year) if year else None,
        },
        "num_citations": citations,
    }
    if doi:
        pub["bib"]["doi"] = doi
    return pub


@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search(mock_search_pubs):
    mock_search_pubs.return_value = [
        _fake_scholarly_pub("Paper Alpha", ["Smith, J.", "Jones, K."], 2022, "10.1000/alpha", 15),
        _fake_scholarly_pub("Paper Beta", ["Lee, M."], 2023),
    ]

    source = ScholarSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=5)

    assert len(papers) == 2
    assert papers[0].title == "Paper Alpha"
    assert papers[0].authors == ["Smith, J.", "Jones, K."]
    assert papers[0].date.year == 2022
    assert papers[0].doi == "10.1000/alpha"
    assert papers[0].citations == 15
    assert papers[0].source == "scholar"


@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_error_fallback(mock_search_pubs):
    mock_search_pubs.side_effect = Exception("Blocked")

    source = ScholarSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=5)
    assert papers == []


# --- Scholar proxy integration tests ---

@patch("core.proxy.ProxyGenerator")
@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_with_proxy_manager_setup(mock_search_pubs, mock_pg):
    """When proxy_manager is set and free_mode=on, search calls FreeProxies."""
    mock_pg.return_value = MagicMock()
    mock_search_pubs.return_value = []
    from core.proxy import ProxyManager
    config = {"proxy": {"http": None, "https": None, "free_mode": "on"}}
    pm = ProxyManager(config)
    source = ScholarSource(delay_min=0, delay_max=0, proxy_manager=pm)
    source.search("test", max_results=5)
    assert pm.using_free_proxy is True


@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_without_proxy_manager_backward_compat(mock_search_pubs):
    """ScholarSource without proxy_manager works as before."""
    mock_search_pubs.return_value = [
        _fake_scholarly_pub("Paper Alpha", ["Smith, J."], 2022, "10.1000/alpha", 15),
    ]
    source = ScholarSource(delay_min=0, delay_max=0)
    papers = source.search("test", max_results=5)
    assert len(papers) == 1
    assert papers[0].title == "Paper Alpha"


@patch("core.proxy.ProxyGenerator")
@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_auto_mode_no_static_uses_free_preemptively(mock_search_pubs, mock_pg):
    """Auto mode with no static proxy: FreeProxies enabled proactively by setup_scholarly."""
    mock_pg.return_value = MagicMock()
    mock_search_pubs.return_value = []
    from core.proxy import ProxyManager
    config = {"proxy": {"http": None, "https": None, "free_mode": "auto"}}
    pm = ProxyManager(config)
    source = ScholarSource(delay_min=0, delay_max=0, proxy_manager=pm)
    source.search("test", max_results=5)
    assert pm.using_free_proxy is True


@patch("core.proxy.ProxyGenerator")
@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_rate_limited_switches_proxy(mock_search_pubs, mock_pg):
    """When search gets rate-limited with static proxy in auto mode,
    on_rate_limited() triggers the free proxy switch."""
    mock_pg.return_value = MagicMock()
    mock_search_pubs.side_effect = Exception("HTTP 429 Too Many Requests")
    from core.proxy import ProxyManager
    config = {"proxy": {"http": "http://static:8080", "https": "http://static:8080", "free_mode": "auto"}}
    pm = ProxyManager(config)
    assert pm.using_free_proxy is False
    source = ScholarSource(delay_min=0, delay_max=0, proxy_manager=pm)
    papers = source.search("test", max_results=5)
    assert papers == []  # graceful fallback
    assert pm.using_free_proxy is True  # on_rate_limited() triggered the switch


@patch("core.proxy.ProxyGenerator")
@patch("core.sources.scholar.scholarly.search_pubs")
def test_scholar_search_network_error_does_not_switch_proxy(mock_search_pubs, mock_pg):
    """Non-rate-limit errors (e.g. network timeout) should NOT trigger proxy switch."""
    mock_pg.return_value = MagicMock()
    mock_search_pubs.side_effect = Exception("Network timeout")
    from core.proxy import ProxyManager
    config = {"proxy": {"http": "http://static:8080", "https": "http://static:8080", "free_mode": "auto"}}
    pm = ProxyManager(config)
    assert pm.using_free_proxy is False
    source = ScholarSource(delay_min=0, delay_max=0, proxy_manager=pm)
    papers = source.search("test", max_results=5)
    assert papers == []  # graceful fallback
    assert pm.using_free_proxy is False  # proxy should NOT switch for network errors
