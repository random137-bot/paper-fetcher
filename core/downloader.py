import logging
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from core.models import Paper

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip().strip(".")
    if len(name) > 200:
        name = name[:200].rsplit(" ", 1)[0]
    return name


def build_filename(paper: Paper) -> str:
    date_str = paper.date.isoformat() if paper.date else "nodate"
    safe_title = sanitize_filename(paper.title)
    # Append DOI (or arXiv ID) in brackets for uniqueness
    identifier = ""
    if paper.doi:
        identifier = " [" + paper.doi.replace("/", "_") + "]"
    elif paper.eprint_url:
        m = re.search(r"arxiv\.org/abs/([^/\s?#]+)", paper.eprint_url)
        if m:
            identifier = " [arXiv:" + m.group(1) + "]"
    return f"{date_str} {safe_title}{identifier}.pdf"


# ---------------------------------------------------------------------------
# Downloader class — session reuse, BS4-based URL extraction, exponential
# backoff, and Content-Type validation (patterns borrowed from scihub.py).
# ---------------------------------------------------------------------------

class _Downloader:
    """Internal downloader with a persistent session (reused across calls)."""

    def __init__(self, domains: list[str], timeout: int = 60, proxy_manager=None):
        if not domains:
            raise ValueError("domains parameter is required")
        self.domains = domains
        self.timeout = timeout
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": _USER_AGENT})
        if proxy_manager:
            proxy_manager.configure_session(self.sess)
        self._available_domains = list(domains)
        self._probed = False

    def _probe_domains(self) -> None:
        """Probe all configured Sci-Hub domains once per session.

        Tests each domain with a quick HEAD request. Available domains
        are cached in self._available_domains for the session lifetime.
        Falls back to the full domain list if all probes fail.
        """
        available: list[str] = []
        for domain in self.domains:
            try:
                resp = self.sess.head(domain, timeout=5)
                if 200 <= resp.status_code < 400:
                    available.append(domain)
                    logger.debug("Domain probe OK: %s (%d)", domain, resp.status_code)
                else:
                    logger.debug("Domain probe skipped: %s (status %d)", domain, resp.status_code)
            except Exception as exc:
                logger.debug("Domain probe failed: %s (%s)", domain, exc)

        if available:
            self._available_domains = available
        else:
            # All probes failed — keep original list as fallback
            self._available_domains = list(self.domains)
            logger.debug("All domain probes failed, keeping original list")

    def _ensure_probed(self) -> None:
        """Lazy probe — only runs on first download attempt, not at construction."""
        if not self._probed:
            self._probe_domains()
            self._probed = True

    def fetch_pdf(self, paper: Paper, output_dir: Path) -> Optional[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / build_filename(paper)

        # Skip if already exists and seems valid
        if out_path.exists() and out_path.stat().st_size > 1024:
            logger.debug("Skipping %s (already exists)", out_path.name)
            return out_path

        # Also check by DOI — another download may have saved the same paper
        # under a slightly different title (dedup across sources).
        if paper.doi:
            doi_safe = paper.doi.replace("/", "_")
            for existing in output_dir.glob("*.pdf"):
                if doi_safe in existing.stem:
                    logger.debug("Skipping %s (DOI matched %s)", out_path.name, existing.name)
                    return existing

        # Step 0: try direct arXiv download first (fast, no Sci-Hub needed)
        success = self._try_arxiv_direct(paper, out_path)
        if success and self._verify_pdf(success):
            return success

        # Step 1: try each query against Sci-Hub (DOI → eprint → pub → url)
        for query in self._build_query_chain(paper):
            success = self._try_domains(query, out_path)
            if success and self._verify_pdf(success):
                return success

        # Step 2: if Sci-Hub failed, try direct download from PDF-looking URLs
        success = self._try_direct_urls(paper, out_path)
        if success and self._verify_pdf(success):
            return success

        return None

    @staticmethod
    def _arxiv_to_pdf_url(eprint_url: str) -> Optional[str]:
        """
        Convert an arXiv abstract URL (e.g. http://arxiv.org/abs/2310.14230v3)
        to a direct PDF URL (https://arxiv.org/pdf/2310.14230v3.pdf).
        """
        m = re.search(r'arxiv\.org/abs/([^/\s?#]+)', eprint_url)
        if m:
            arxiv_id = m.group(1)
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        return None

    def _try_arxiv_direct(self, paper: Paper, out_path: Path) -> Optional[Path]:
        """Try to download directly from arXiv if the paper has an eprint URL."""
        if not paper.eprint_url:
            return None
        pdf_url = self._arxiv_to_pdf_url(paper.eprint_url)
        if not pdf_url:
            return None

        logger.debug("Trying direct arXiv download from %s", pdf_url)
        try:
            resp = self.sess.get(pdf_url, timeout=self.timeout, stream=True)
            if resp.status_code != 200:
                logger.debug("arXiv returned status %d", resp.status_code)
                return None

            tmp_path = out_path.with_suffix(".tmp")
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(tmp_path, "rb") as f:
                if not f.read(4).startswith(b"%PDF"):
                    tmp_path.unlink(missing_ok=True)
                    logger.debug("arXiv response is not a PDF")
                    return None

            tmp_path.rename(out_path)
            logger.info("Direct download from arXiv: %s", pdf_url)
            return out_path
        except Exception as exc:
            logger.debug("arXiv direct download failed: %s", exc)
            return None

    @staticmethod
    def _build_query_chain(paper: Paper) -> list[str]:
        """
        Build ordered list of queries to try against Sci-Hub.
        Pattern borrowed from scihub.py's _classify → _get_direct_url approach:
        Sci-Hub accepts DOIs, PMIDs, and arbitrary URLs as identifiers.
        """
        seen: set[str] = set()
        queries: list[str] = []

        def add(q: str | None):
            if q and q not in seen:
                seen.add(q)
                queries.append(q)

        add(paper.doi)
        add(paper.title)
        add(paper.eprint_url)   # e.g. https://arxiv.org/abs/2401.12345
        add(paper.pub_url)      # e.g. https://doi.org/10.xxxx/xxxxx
        add(paper.url)          # e.g. Semantic Scholar URL
        return queries

    @staticmethod
    def _is_direct_pdf_url(url: str) -> bool:
        """
        Check if a URL looks like a direct PDF link (scihub.py's _classify pattern).
        scihub.py checks: .pdf, /pdf/, /download, pdf=, ?pdf
        """
        pdf_indicators = [".pdf", "/pdf/", "/download", "pdf=", "?pdf"]
        return any(indicator in url.lower() for indicator in pdf_indicators)

    def _try_direct_urls(self, paper: Paper, out_path: Path) -> Optional[Path]:
        """
        Try direct download from saved URLs that look like direct PDF links.
        This avoids Sci-Hub entirely for openly accessible papers.
        """
        for url in [paper.eprint_url, paper.pub_url, paper.url]:
            if not url or not self._is_direct_pdf_url(url):
                continue
            logger.debug("Trying direct download from %s", url)
            try:
                resp = self.sess.get(url, timeout=self.timeout, stream=True)
                if resp.status_code != 200:
                    continue

                tmp_path = out_path.with_suffix(".tmp")
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                with open(tmp_path, "rb") as f:
                    if not f.read(4).startswith(b"%PDF"):
                        tmp_path.unlink(missing_ok=True)
                        continue

                tmp_path.rename(out_path)
                logger.info("Direct download from %s", url)
                return out_path
            except Exception as exc:
                logger.debug("Direct download failed from %s: %s", url, exc)
                continue
        return None

    @staticmethod
    def _verify_pdf(path: Path) -> bool:
        """Verify that a file starts with the PDF magic bytes."""
        with open(path, "rb") as f:
            if not f.read(4).startswith(b"%PDF"):
                path.unlink(missing_ok=True)
                logger.warning("Not a valid PDF: %s", path.name)
                return False
        return True

    def _try_domains(self, query: str, out_path: Path) -> Optional[Path]:
        """Try all configured domains with exponential backoff (up to 3 attempts)."""
        self._ensure_probed()
        for attempt in range(3):
            for domain in self._available_domains:
                try:
                    result = self._try_single(domain, query, out_path, attempt)
                    if result:
                        return result
                except requests.exceptions.ConnectionError as exc:
                    logger.debug("Connection error on %s (attempt %d): %s", domain, attempt + 1, exc)
                except requests.exceptions.Timeout as exc:
                    logger.debug("Timeout on %s (attempt %d): %s", domain, attempt + 1, exc)
                except Exception as exc:
                    logger.debug("Unexpected error on %s (attempt %d): %s", domain, attempt + 1, exc)

            if attempt < 2:
                backoff = 2 ** attempt  # 1s, 2s — matches scihub.py pattern
                logger.debug("All domains failed on attempt %d; backing off %ds", attempt + 1, backoff)
                time.sleep(backoff)

        return None

    def _try_single(self, domain: str, query: str, out_path: Path, attempt: int) -> Optional[Path]:
        """Try to download from a single Sci-Hub domain."""
        scihub_url = f"{domain}/{query}"
        logger.debug("Trying %s (attempt %d)", scihub_url, attempt + 1)

        resp = self.sess.get(scihub_url, timeout=self.timeout)
        if resp.status_code != 200:
            return None

        pdf_url = self._extract_pdf_url(resp.text, domain)
        if not pdf_url:
            logger.debug("No PDF URL found in response from %s", scihub_url)
            return None

        # Content-Type validation (borrowed from scihub.py) — early rejection
        pdf_resp = self.sess.get(pdf_url, timeout=self.timeout, stream=True)
        content_type = pdf_resp.headers.get("Content-Type", "")
        if "application/pdf" not in content_type and "octet-stream" not in content_type:
            logger.debug("Unexpected Content-Type '%s' from %s", content_type, pdf_url)
            # Don't bail yet — some Sci-Hub instances serve PDF with wrong Content-Type

        tmp_path = out_path.with_suffix(".tmp")
        with open(tmp_path, "wb") as f:
            for chunk in pdf_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Validate PDF header
        with open(tmp_path, "rb") as f:
            header = f.read(4)
        if not header.startswith(b"%PDF"):
            tmp_path.unlink(missing_ok=True)
            logger.debug("Invalid PDF header from %s", pdf_url)
            return None

        tmp_path.rename(out_path)
        logger.info("Downloaded from %s (domain: %s)", pdf_url, domain)
        return out_path

    @staticmethod
    def _extract_pdf_url(html: str, base_domain: str) -> Optional[str]:
        """
        Extract PDF URL from Sci-Hub HTML using BeautifulSoup (like scihub.py).
        Checks iframe → embed → <a> tags with .pdf → any <a> tag.
        """
        soup = BeautifulSoup(html, "html.parser")

        # 1) Iframe (most common pattern on Sci-Hub)
        iframe = soup.find("iframe", src=True)
        if iframe:
            return _resolve_url(iframe["src"], base_domain)

        # 2) Embed tag
        embed = soup.find("embed", src=True)
        if embed:
            return _resolve_url(embed["src"], base_domain)

        # 3) <a> tag with explicit .pdf href
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                return _resolve_url(href, base_domain)

        # 4) location.href redirect (fallback)
        m = re.search(r"""location\.href\s*=\s*["']([^"']+)""", html)
        if m:
            return _resolve_url(m.group(1), base_domain)

        return None

    def close(self):
        self.sess.close()


def _resolve_url(url: str, base_domain: str) -> str:
    """Resolve relative/protocol-relative URLs to absolute."""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base_domain.rstrip("/") + url
    if not url.startswith("http"):
        return base_domain.rstrip("/") + "/" + url
    return url


# ---------------------------------------------------------------------------
# Public function API (creates a new Downloader per call)
# ---------------------------------------------------------------------------


def download(
    paper: Paper,
    output_dir: Path,
    domains: list[str],
    timeout: int = 60,
    proxy_manager=None,
) -> Optional[Path]:
    """Download a paper from Sci-Hub."""
    dl = _Downloader(domains, timeout, proxy_manager=proxy_manager)
    try:
        return dl.fetch_pdf(paper, output_dir)
    finally:
        dl.close()
