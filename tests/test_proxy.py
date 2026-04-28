from unittest.mock import patch, MagicMock
from core.proxy import ProxyManager


def test_proxy_manager_off_mode():
    config = {"proxy": {"http": None, "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    assert pm.free_mode == "off"
    assert pm.using_free_proxy is False


def test_proxy_manager_on_mode_initially_not_using_free():
    config = {"proxy": {"http": None, "https": None, "free_mode": "on"}}
    pm = ProxyManager(config)
    assert pm.using_free_proxy is False  # Will be True after setup_scholarly


def test_configure_session_http_only_mirrors_to_https():
    """When only http proxy is set, https should mirror it."""
    import requests
    config = {"proxy": {"http": "http://proxy:8080", "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    session = requests.Session()
    pm.configure_session(session)
    assert session.proxies.get("http") == "http://proxy:8080"
    assert session.proxies.get("https") == "http://proxy:8080"


def test_configure_session_https_only_mirrors_to_http():
    """When only https proxy is set, http should mirror it."""
    import requests
    config = {"proxy": {"http": None, "https": "https://proxy:8443", "free_mode": "off"}}
    pm = ProxyManager(config)
    session = requests.Session()
    pm.configure_session(session)
    assert session.proxies.get("https") == "https://proxy:8443"
    assert session.proxies.get("http") == "https://proxy:8443"


def test_configure_session_both_proxies_no_mirroring():
    """When both proxies are set, they should appear as distinct entries."""
    import requests
    config = {"proxy": {"http": "http://http-proxy:8080", "https": "https://https-proxy:8443", "free_mode": "off"}}
    pm = ProxyManager(config)
    session = requests.Session()
    pm.configure_session(session)
    assert session.proxies.get("http") == "http://http-proxy:8080"
    assert session.proxies.get("https") == "https://https-proxy:8443"


def test_proxy_manager_auto_mode():
    config = {"proxy": {"http": None, "https": None, "free_mode": "auto"}}
    pm = ProxyManager(config)
    assert pm.free_mode == "auto"
    assert pm.using_free_proxy is False


def test_proxy_manager_static_http_proxy():
    config = {"proxy": {"http": "http://127.0.0.1:8080", "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    assert pm.http_proxy == "http://127.0.0.1:8080"
    assert pm.https_proxy is None


def test_configure_session_off_mode_with_static_proxy():
    import requests
    config = {"proxy": {"http": "http://127.0.0.1:8080", "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    session = requests.Session()
    pm.configure_session(session)
    assert session.proxies.get("http") == "http://127.0.0.1:8080"


def test_configure_session_off_mode_no_proxy():
    import requests
    config = {"proxy": {"http": None, "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    session = requests.Session()
    pm.configure_session(session)
    assert session.proxies.get("http") is None


def test_on_rate_limited_switches_to_free_in_auto_mode():
    """In auto mode, on_rate_limited should trigger free proxy switch."""
    with patch("core.proxy.ProxyGenerator") as mock_pg_cls:
        mock_pg = MagicMock()
        mock_pg_cls.return_value = mock_pg
        config = {"proxy": {"http": None, "https": None, "free_mode": "auto"}}
        pm = ProxyManager(config)
        assert pm.using_free_proxy is False
        pm.on_rate_limited()
        assert pm.using_free_proxy is True
        mock_pg.FreeProxies.assert_called_once()


def test_on_rate_limited_noop_in_off_mode():
    with patch("core.proxy.ProxyGenerator") as mock_pg_cls:
        config = {"proxy": {"http": None, "https": None, "free_mode": "off"}}
        pm = ProxyManager(config)
        pm.on_rate_limited()
        assert pm.using_free_proxy is False
        mock_pg_cls.assert_not_called()


def test_on_rate_limited_noop_when_already_free():
    with patch("core.proxy.ProxyGenerator") as mock_pg_cls:
        mock_pg = MagicMock()
        mock_pg_cls.return_value = mock_pg
        config = {"proxy": {"http": None, "https": None, "free_mode": "auto"}}
        pm = ProxyManager(config)
        pm.on_rate_limited()  # first call switches
        pm.on_rate_limited()  # second call should be noop (already free)
        assert pm.using_free_proxy is True
        assert mock_pg_cls.call_count == 1  # ProxyGenerator created only once


@patch("core.proxy.ProxyGenerator")
def test_setup_scholarly_on_mode(mock_pg_cls):
    mock_pg = MagicMock()
    mock_pg_cls.return_value = mock_pg
    config = {"proxy": {"http": None, "https": None, "free_mode": "on"}}
    pm = ProxyManager(config)
    pm.setup_scholarly()
    mock_pg.FreeProxies.assert_called_once()
    assert pm.using_free_proxy is True


@patch("core.proxy.ProxyGenerator")
def test_setup_scholarly_off_mode_skips(mock_pg_cls):
    config = {"proxy": {"http": None, "https": None, "free_mode": "off"}}
    pm = ProxyManager(config)
    pm.setup_scholarly()
    mock_pg_cls.assert_not_called()


@patch("core.proxy.ProxyGenerator")
def test_setup_scholarly_auto_mode_with_static_proxy_skips(mock_pg_cls):
    """In auto mode with static proxy, don't set up free proxy initially."""
    config = {"proxy": {"http": "http://127.0.0.1:8080", "https": None, "free_mode": "auto"}}
    pm = ProxyManager(config)
    pm.setup_scholarly()
    mock_pg_cls.assert_not_called()


@patch("core.proxy.ProxyGenerator")
def test_setup_scholarly_auto_mode_no_static_proxy_uses_free(mock_pg_cls):
    """In auto mode with no static proxy, use free proxy from the start."""
    mock_pg = MagicMock()
    mock_pg_cls.return_value = mock_pg
    config = {"proxy": {"http": None, "https": None, "free_mode": "auto"}}
    pm = ProxyManager(config)
    pm.setup_scholarly()
    mock_pg.FreeProxies.assert_called_once()


@patch("core.proxy.ProxyGenerator")
def test_setup_scholarly_failure_graceful(mock_pg_cls):
    mock_pg_cls.side_effect = Exception("Connection error")
    config = {"proxy": {"http": None, "https": None, "free_mode": "on"}}
    pm = ProxyManager(config)
    pm.setup_scholarly()  # should not raise
    assert pm.using_free_proxy is False
