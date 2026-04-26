from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import date
from core.models import Paper
from core.downloader import sanitize_filename, build_filename


def test_sanitize_filename():
    assert sanitize_filename('Paper: "Title" <with> chars') == "Paper Title with chars"
    assert sanitize_filename("A/B/C: Test") == "ABC Test"
    result = sanitize_filename("x" * 300)
    assert len(result) <= 200


def test_build_filename():
    p = Paper(title="Deep Learning 101", date=date(2024, 6, 15))
    name = build_filename(p)
    assert name.startswith("2024-06-15")
    assert "Deep Learning 101" in name
    assert name.endswith(".pdf")


def test_build_filename_no_date():
    p = Paper(title="Unknown Date Paper")
    name = build_filename(p)
    assert name.startswith("nodate")
    assert "Unknown Date Paper" in name


@patch("core.downloader.time.sleep")
@patch("core.downloader.requests.Session")
def test_download_validation_bad_pdf(mock_session_class, mock_sleep):
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"not a pdf"]
    mock_resp.text = '<iframe src="//sci-hub.se/pdf/bad.pdf"></iframe>'
    mock_session.get.return_value = mock_resp

    from core.downloader import download
    p = Paper(title="Test", doi="10.0/test")
    result = download(p, Path("/tmp/test_dl_bad"), domains=["https://sci-hub.se"])
    assert result is None


@patch("core.downloader.time.sleep")
@patch("core.downloader.requests.Session")
def test_download_success(mock_session_class, mock_sleep):
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"%PDF-1.4", b"more content"]
    mock_resp.text = '<iframe src="//sci-hub.se/pdf/abc.pdf"></iframe>'
    mock_session.get.return_value = mock_resp

    from core.downloader import download
    p = Paper(title="Test Paper", date=date(2024, 1, 1), doi="10.0/test")
    result = download(p, Path("/tmp/test_dl_ok"), domains=["https://sci-hub.se"])
    assert result is not None
    assert result.name == "2024-01-01 Test Paper [10.0_test].pdf"


@patch("core.downloader.Path.exists", return_value=True)
@patch("core.downloader.Path.mkdir")
@patch("core.downloader.Path.stat")
def test_download_skip_existing(mock_stat, mock_mkdir, mock_exists):
    from core.downloader import download
    mock_stat.return_value.st_size = 5000
    p = Paper(title="Existing Paper", date=date(2024, 1, 1), doi="10.0/test")
    result = download(p, Path("/tmp"), domains=["https://sci-hub.se"])
    assert result == Path("/tmp/2024-01-01 Existing Paper [10.0_test].pdf")
