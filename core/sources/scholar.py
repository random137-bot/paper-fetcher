from scholarly import scholarly
from core.sources.base import BaseSource
from core.models import Paper
from datetime import date as dt_date


class ScholarSource(BaseSource):
    name = "scholar"

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        try:
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
        except Exception:
            return []
