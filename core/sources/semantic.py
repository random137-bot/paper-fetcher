import logging
from datetime import date as dt_date
from semanticscholar import SemanticScholar
from core.sources.base import BaseSource
from core.models import Paper

logger = logging.getLogger(__name__)


class SemanticSource(BaseSource):
    name = "semantic"

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.client = SemanticScholar(api_key=api_key)

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        try:
            self.limiter.wait()
            results = self.client.search_paper(
                topic,
                limit=max_results,
                fields=[
                    "title", "authors", "year", "externalIds",
                    "citationCount", "url", "abstract",
                ],
            )
        except Exception as exc:
            logger.warning("Semantic Scholar API error: %s", exc)
            return []

        papers = []
        for paper in results:
            ext_ids = paper.externalIds or {}
            papers.append(Paper(
                title=paper.title or "",
                authors=[a.name for a in paper.authors] if paper.authors else [],
                date=dt_date(paper.year, 1, 1) if paper.year else None,
                doi=ext_ids.get("DOI"),
                citations=paper.citationCount,
                source=self.name,
                url=paper.url or "",
                abstract=(paper.abstract or "").strip(),
                pub_url=paper.url or "",
                eprint_url=(
                    f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
                    if ext_ids.get("ArXiv") else ""
                ),
            ))
        return papers
