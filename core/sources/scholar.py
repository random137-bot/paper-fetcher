from scholarly import scholarly
from core.sources.base import BaseSource
from core.models import Paper
from datetime import date as dt_date
import logging

logger = logging.getLogger(__name__)


class ScholarSource(BaseSource):
    name = "scholar"

    def __init__(self, delay_min: float = 10.0, delay_max: float = 20.0,
                 proxy_manager=None):
        super().__init__(delay_min, delay_max)
        self.proxy_manager = proxy_manager

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        try:
            if self.proxy_manager:
                self.proxy_manager.setup_scholarly()

            search_query = scholarly.search_pubs(topic)
            papers = []
            for i, pub in enumerate(search_query):
                if i >= max_results:
                    break
                try:
                    self.limiter.wait()
                    bib = pub.get("bib", {})
                    title = bib.get("title", "")
                    authors = bib.get("author", [])
                    if not isinstance(authors, list):
                        authors = [authors] if authors else []
                    year_str = bib.get("pub_year")
                    doi = bib.get("doi")
                    citations = pub.get("num_citations")
                    abstract = (bib.get("abstract") or "").strip()
                    ep = bib.get("eprint", "")
                    eprint_url = f"https://arxiv.org/abs/{ep}" if ep else ""
                    pdate = None
                    if year_str:
                        try:
                            pdate = dt_date(int(year_str), 1, 1)
                        except (ValueError, TypeError):
                            pass
                    papers.append(Paper(
                        title=title,
                        authors=authors,
                        date=pdate,
                        doi=doi,
                        citations=citations,
                        source=self.name,
                        url=bib.get("url", ""),
                        abstract=abstract,
                        eprint_url=eprint_url,
                    ))
                except Exception:
                    continue
            return papers
        except Exception as exc:
            logger.warning("Scholar search error: %s", exc)
            if self.proxy_manager:
                # Only trigger proxy switch on rate-limit errors, not all failures
                msg = str(exc).lower()
                if any(indicator in msg for indicator in ("429", "rate limit", "too many")):
                    self.proxy_manager.on_rate_limited()
            return []
