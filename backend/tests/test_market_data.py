"""Testy pre app/services/market_data.py — agregaciu sprav z viacerych
zdrojov (get_crypto_headlines) a Reddit integraciu (get_reddit_crypto_posts).
Kazdy zdroj musi byt izolovany - vypadok jedneho nesmie zhodit zvysne."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import market_data  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_headlines_cache():
    """get_crypto_headlines() cachuje vysledok - bez vycistenia by jeden test
    dostal cachovany vysledok z predchadzajuceho testu."""
    market_data._headlines_cache._store.clear()
    yield
    market_data._headlines_cache._store.clear()


def _rss_xml(title: str, item_titles: list) -> bytes:
    items = "".join(
        f"<item><title>{t}</title><link>https://example.com/{i}</link>"
        f"<pubDate>Mon, 01 Jan 2026 0{i}:00:00 GMT</pubDate></item>"
        for i, t in enumerate(item_titles)
    )
    return f"<rss><channel><title>{title}</title>{items}</channel></rss>".encode("utf-8")


class _FakeResponse:
    def __init__(self, content=b"", status_code=200, json_data=None):
        self.content = content
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise market_data.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def test_headlines_degrade_gracefully_when_one_rss_source_fails(monkeypatch):
    """Ak jeden feed (napr. CoinTelegraph) padne, ostatne zdroje musia aj tak
    vratit spravy - pouzivatel nesmie vidiet uplny vypadok kvoli jednemu
    docasne nedostupnemu webu."""
    urls = market_data.CRYPTO_NEWS_RSS_URLS
    assert len(urls) >= 2, "test predpoklada aspon 2 nakonfigurovane RSS zdroje"

    def fake_get(url, timeout=None, headers=None):
        if url == urls[0]:
            raise market_data.requests.exceptions.ConnectionError("simulovany vypadok")
        return _FakeResponse(content=_rss_xml("Funkcny Zdroj", ["Titulok A", "Titulok B"]))

    monkeypatch.setattr(market_data.requests, "get", fake_get)
    monkeypatch.setattr(market_data, "get_reddit_crypto_posts", lambda limit=3: [])

    ok, headlines, error = market_data.get_crypto_headlines(limit=8)
    assert ok is True
    assert len(headlines) > 0
    assert error is None


def test_headlines_fail_only_when_every_source_fails(monkeypatch):
    def fake_get(*a, **k):
        raise market_data.requests.exceptions.ConnectionError("vsetko padlo")

    monkeypatch.setattr(market_data.requests, "get", fake_get)
    monkeypatch.setattr(market_data, "get_reddit_crypto_posts", lambda limit=3: [])

    ok, headlines, error = market_data.get_crypto_headlines(limit=8)
    assert ok is False
    assert headlines == []
    assert error is not None


def test_headlines_include_reddit_when_available(monkeypatch):
    monkeypatch.setattr(
        market_data.requests, "get",
        lambda url, timeout=None, headers=None: _FakeResponse(content=_rss_xml("Zdroj", ["RSS titulok"])),
    )
    monkeypatch.setattr(
        market_data, "get_reddit_crypto_posts",
        lambda limit=3: [{"title": "Reddit post", "link": "https://reddit.com/x", "source": "r/CryptoCurrency", "published_at": ""}],
    )
    ok, headlines, _ = market_data.get_crypto_headlines(limit=20)
    assert ok is True
    assert any(h["source"] == "r/CryptoCurrency" for h in headlines)


def test_reddit_posts_never_raises_on_network_failure(monkeypatch):
    def fake_get(*a, **k):
        raise market_data.requests.exceptions.ConnectionError("reddit nedostupny")

    monkeypatch.setattr(market_data.requests, "get", fake_get)
    result = market_data.get_reddit_crypto_posts()
    assert result == []


def test_reddit_posts_skip_stickied_entries(monkeypatch):
    fake_body = {
        "data": {
            "children": [
                {"data": {"title": "Pravidla subredditu", "stickied": True, "permalink": "/r/x/1", "created_utc": 1700000000}},
                {"data": {"title": "Realny post o BTC", "stickied": False, "permalink": "/r/x/2", "created_utc": 1700000001}},
            ]
        }
    }
    monkeypatch.setattr(
        market_data.requests, "get",
        lambda url, timeout=None, headers=None: _FakeResponse(json_data=fake_body),
    )
    result = market_data.get_reddit_crypto_posts()
    assert len(result) == 1
    assert result[0]["title"] == "Realny post o BTC"
