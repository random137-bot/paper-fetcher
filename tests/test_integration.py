"""End-to-end pipeline tests."""
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock


def test_full_pipeline_search_save_parse():
    """Test: core search (mocked) -> save results -> parse results -> verify."""
    from core.models import Paper
    from core.storage import save_results, parse_results

    papers = [
        Paper(title="Pipeline Test Paper", authors=["Author One", "Author Two"],
              date=date(2024, 3, 15), doi="10.9999/pipeline", citations=42, source="test"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        topic_dir = Path(tmp) / "test-pipeline"
        save_results(topic_dir, "Pipeline Test", papers, ["test"])

        assert (topic_dir / "results.md").exists()
        content = (topic_dir / "results.md").read_text()
        assert "Pipeline Test Paper" in content
        assert "10.9999/pipeline" in content
        assert "42" in content

        parsed = parse_results(topic_dir)
        assert len(parsed) == 1
        assert parsed[0].title == "Pipeline Test Paper"
        assert parsed[0].doi == "10.9999/pipeline"


def test_slugify_consistency():
    """Verify slugify is consistent across storage and merger modules."""
    from core.utils import slugify as s0
    from core.storage import slugify as s1
    from core.merger import slugify as s2

    cases = [
        ("Federated Learning", "federated-learning"),
        ("Deep   Learning", "deep-learning"),
        ("Causal Inference & ML", "causal-inference-ml"),
        ("A/B Testing", "a-b-testing"),
        ("simple", "simple"),
    ]
    for inp, expected in cases:
        assert s0(inp) == expected, f"utils.slugify('{inp}') != '{expected}'"
        assert s1(inp) == expected, f"storage.slugify('{inp}') != '{expected}'"
        assert s2(inp) == expected, f"merger.slugify('{inp}') != '{expected}'"


def test_index_roundtrip():
    """Full cycle: save index -> load index -> verify."""
    from core.storage import save_index, load_index
    from core.models import TopicInfo

    index = {
        "test-topic": TopicInfo(path="test-topic", keywords=["test", "topic"],
                                paper_count=5, last_updated="2026-01-01T00:00:00"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        save_index(base, index)
        # load_index filters out entries whose topic directory doesn't exist
        (base / "test-topic").mkdir()
        loaded = load_index(base)

        assert "test-topic" in loaded
        assert loaded["test-topic"].paper_count == 5
        assert loaded["test-topic"].keywords == ["test", "topic"]


def test_searcher_dedup_pipeline():
    """Test that search -> dedup works with real-like Paper objects."""
    from core.searcher import deduplicate
    from core.models import Paper

    p1 = Paper(title="  Same Paper.", doi="10.0/dup", citations=10, source="arxiv")
    p2 = Paper(title="Same Paper", doi="10.0/DUP", source="semantic")
    result = deduplicate([p1, p2])
    assert len(result) == 1
    assert result[0].citations == 10
