import logging
from core.sources.base import BaseSource
from core.models import Paper
from datetime import date as dt_date

logger = logging.getLogger(__name__)


class SemanticSource(BaseSource):
    name = "semantic"
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        params = {
            "query": topic,
            "limit": min(max_results, 100),
            "fields": "title,authors,year,externalIds,citationCount,url,abstract",
        }
        try:
            resp = self._request_with_retry(self.BASE_URL, params=params, headers=headers)
        except Exception as e:
            logger.warning("Semantic Scholar API error: %s", e)
            print(f"[semantic] Error: {e}")
            return []
        if resp is None:
            print("[semantic] Request failed after retries — skipping Semantic Scholar.")
            return []
        data = resp.json()

        papers = []
        for item in data.get("data", []):
            authors = [a["name"] for a in item.get("authors", [])]
            doi = None
            ext_ids = item.get("externalIds") or {}
            if "DOI" in ext_ids:
                doi = ext_ids["DOI"]
            year = item.get("year")
            pdate = dt_date(year, 1, 1) if year else None
            abstract = (item.get("abstract") or "").strip()
            pub_url = item.get("url", "")
            eprint_url = ""
            if "ArXiv" in ext_ids:
                eprint_url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
            elif "CorpusId" in ext_ids and not pub_url:
                pub_url = f"https://www.semanticscholar.org/paper/{ext_ids['CorpusId']}"
            papers.append(Paper(
                title=item.get("title", ""),
                authors=authors,
                date=pdate,
                doi=doi,
                citations=item.get("citationCount"),
                source=self.name,
                url=pub_url,
                abstract=abstract,
                pub_url=pub_url,
                eprint_url=eprint_url,
            ))
        return papers
