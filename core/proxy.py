import logging
import requests
from scholarly import ProxyGenerator, scholarly

logger = logging.getLogger(__name__)


class ProxyManager:
    """Centralized proxy lifecycle manager.

    Modes (proxy.free_mode):
      - "off": Only use static proxy (http/https from config), never use FreeProxies.
      - "on":  Always use FreeProxies, ignore static proxy.
      - "auto": Prefer static proxy; switch to FreeProxies on rate-limit detection.
    """

    def __init__(self, config: dict):
        proxy_cfg = config.get("proxy", {})
        self.http_proxy = proxy_cfg.get("http")
        self.https_proxy = proxy_cfg.get("https")
        self.free_mode = proxy_cfg.get("free_mode", "auto")
        self._using_free = False

    @property
    def using_free_proxy(self) -> bool:
        return self._using_free

    @property
    def _has_static_proxy(self) -> bool:
        return bool(self.http_proxy or self.https_proxy)

    def _get_static_proxies(self) -> dict | None:
        """Build the proxies dict for requests.Session from static config."""
        proxies = {}
        if self.http_proxy:
            proxies["http"] = self.http_proxy
        if self.https_proxy:
            proxies["https"] = self.https_proxy
        # Also set the matching protocol if only one is configured
        if self.http_proxy and not self.https_proxy:
            proxies["https"] = self.http_proxy
        if self.https_proxy and not self.http_proxy:
            proxies["http"] = self.https_proxy
        return proxies if proxies else None

    def configure_session(self, session: requests.Session) -> None:
        """Apply static proxy settings to a requests.Session.

        FreeProxies are managed by scholarly internally and do not apply
        to raw requests sessions. Only static config proxies are used here.
        """
        proxies = self._get_static_proxies()
        if proxies:
            session.proxies.update(proxies)

    def setup_scholarly(self) -> None:
        """Set up scholarly with appropriate proxy strategy."""
        if self.free_mode == "off":
            return

        if self.free_mode == "on":
            self._enable_scholarly_free_proxy()
            return

        # "auto" mode
        if not self._has_static_proxy:
            # No static proxy configured, use free proxy from the start
            self._enable_scholarly_free_proxy()

    def on_rate_limited(self) -> None:
        """Called when rate limiting is detected. Switches to free proxy if in auto mode."""
        if self.free_mode == "off" or self._using_free:
            return
        logger.info("Rate limit detected, switching to free proxy mode")
        self._enable_scholarly_free_proxy()

    def _enable_scholarly_free_proxy(self) -> None:
        """Set up scholarly's ProxyGenerator with FreeProxies."""
        try:
            pg = ProxyGenerator()
            pg.FreeProxies()
            scholarly.use_proxy(pg, pg)
            self._using_free = True
            logger.info("FreeProxies activated for scholarly")
        except Exception as exc:
            logger.warning("Failed to set up FreeProxies: %s", exc)
