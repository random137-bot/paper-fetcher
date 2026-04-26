import logging
import random
import time
from abc import ABC, abstractmethod
import requests
from core.models import Paper

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, delay_min: float, delay_max: float):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._last_call: float = time.monotonic()

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last_call
        needed = random.uniform(self.delay_min, self.delay_max)
        if elapsed < needed:
            time.sleep(needed - elapsed)
        self._last_call = time.monotonic()


class BaseSource(ABC):
    name: str = "base"

    def __init__(self, delay_min: float = 1.0, delay_max: float = 3.0):
        self.limiter = RateLimiter(delay_min, delay_max)

    def _request_with_retry(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> requests.Response | None:
        """Make an HTTP GET with exponential backoff on 429 rate limits.

        Returns the response on success, or None if all retries are exhausted.
        """
        for attempt in range(max_retries + 1):
            self.limiter.wait()
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            except requests.exceptions.RequestException:
                if attempt < max_retries:
                    wait = 5 * (2**attempt)
                    logger.warning(
                        "[%s] Request failed (attempt %d/%d), retrying in %ds ...",
                        self.name, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
                raise

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (2**attempt)
                logger.warning(
                    "[%s] Rate limited (429, attempt %d/%d), retrying in %ds ...",
                    self.name, attempt + 1, max_retries, wait,
                )
                if attempt < max_retries:
                    time.sleep(wait)
                    continue
                return None

            resp.raise_for_status()
            return resp

        return None

    @abstractmethod
    def search(self, topic: str, max_results: int = 20) -> list[Paper]:
        ...
