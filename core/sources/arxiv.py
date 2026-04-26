from core.sources.base import BaseSource
from core.models import Paper
import arxiv


class ArxivSource(BaseSource):
    name = "arxiv"

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        try:
            self.limiter.wait()
            client = arxiv.Client()
            search = arxiv.Search(
                query=topic,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            results = list(client.results(search))
        except Exception:
            return []

        papers = []
        for r in results:
            papers.append(Paper(
                title=r.title,
                authors=[a.name for a in r.authors] if r.authors else [],
                date=r.published.date() if r.published else None,
                doi=r.doi,
                source=self.name,
                url=r.entry_id,
                abstract=(r.summary or "").strip(),
                eprint_url=r.entry_id,
                pub_url=f"https://doi.org/{r.doi}" if r.doi else "",
            ))
        return papers
