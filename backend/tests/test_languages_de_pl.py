"""German and Polish are fully supported next to English, Slovak and Czech."""

import pytest

from app import i18n_content
from app.models import PriceAlert, User
from app.services import alerts, briefing, demo_data, digest, email_service, signals, validators
from tests.conftest import csrf_headers

MODULES = (i18n_content, alerts, briefing, demo_data, digest, email_service, validators)
NEW_LANGS = ("de", "pl")


def _lang_dicts(value, path):
    """Yield every dict (also nested ones) that is keyed by language, i.e. has a "cs" key."""
    if isinstance(value, dict):
        if "cs" in value:
            yield path, value
        for key, inner in value.items():
            yield from _lang_dicts(inner, f"{path}[{key!r}]")


def _module_lang_dicts():
    for module in MODULES:
        for name, value in vars(module).items():
            if not name.startswith("__"):
                yield from _lang_dicts(value, f"{module.__name__}.{name}")


@pytest.mark.parametrize("path,table", list(_module_lang_dicts()), ids=lambda v: v if isinstance(v, str) else "")
def test_every_language_dict_has_de_and_pl(path, table):
    for lang in NEW_LANGS:
        assert lang in table, f"{path} is missing {lang!r}"
        if isinstance(table["cs"], dict):
            assert set(table[lang]) == set(table["cs"]), f"{path}[{lang!r}] has different keys than cs"
        if isinstance(table["cs"], (list, tuple)):
            assert len(table[lang]) == len(table["cs"]), f"{path}[{lang!r}] has a different length than cs"


def test_language_dicts_were_found():
    assert len(list(_module_lang_dicts())) >= 15


def test_placeholders_are_identical():
    import string

    def fields(text):
        return {f for _, f, _, _ in string.Formatter().parse(text) if f is not None}

    for path, table in _module_lang_dicts():
        for lang in NEW_LANGS:
            cs, other = table["cs"], table[lang]
            pairs = (zip(cs.values(), other.values()) if isinstance(cs, dict)
                     else zip(cs, other) if isinstance(cs, (list, tuple)) else [(cs, other)])
            for a, b in pairs:
                if isinstance(a, str):
                    assert fields(a) == fields(b), f"{path}[{lang!r}]: {b!r}"


def test_normalize_lang():
    assert i18n_content.normalize_lang("de") == "de"
    assert i18n_content.normalize_lang("pl") == "pl"
    assert i18n_content.normalize_lang("fr") == "en"
    assert i18n_content.normalize_lang(None) == "en"
    assert set(i18n_content.SUPPORTED_LANGS) == {"en", "sk", "cs", "de", "pl"}


def test_helpers_translate_and_fall_back():
    assert i18n_content.unit_label("den", "de") == "Tag"
    assert i18n_content.unit_label("mesiac", "pl") == "miesiąc"
    assert i18n_content.missing_api_key_message("xx") == i18n_content.MISSING_API_KEY["en"]
    assert "Fed" in i18n_content.market_events_for_lang("de")["fomc"][0]
    assert "[BEISPIELDATEN]" in i18n_content.mock_forecast_reasoning("BTC", "7 Tage", "up", "de")
    assert "[DANE PRZYKŁADOWE]" in i18n_content.mock_chat_reply("?", "pl")
    assert i18n_content.mock_portfolio_reason("SELL", "ETH", "pl").startswith("[MOCK] ETH")
    assert email_service.email_lang("de") == "de" and email_service.email_lang("xx") == "en"
    assert "deutsch" in validators.language_instruction("de")
    assert "polski" in validators.language_instruction("pl", json_mode=False)
    assert validators.language_instruction("xx").endswith("English. Kluce JSON nemen.")


def test_signal_labels_have_every_language_and_never_index_out_of_range():
    for key, names in signals.LABELS.items():
        assert len(names) == len(i18n_content.SUPPORTED_LANGS), key
    items = [{"key": "liquidations", "tone": "bearish", "display": "$1B"},
             {"key": "unknown_signal", "tone": "bullish", "display": "1"}]
    assert signals.headline(items, "de") == ["Liquidationen: $1B ▼", "unknown_signal: 1 ▲"]
    assert signals.headline(items, "pl")[0] == "Likwidacje: $1B ▼"
    assert signals.headline(items, "xx")[0] == "Liquidations: $1B ▼"


_WEEK = {"total": 12, "hit": 58, "best": {"model": "Gemini", "n": 5, "hit": 80}, "tips_won": 3, "tips_total": 5}
_MINE = {"n": 2, "hits": 1, "won": 1, "lost": 0}
_FOREIGN = ("This week", "Across all users", "Unsubscribe", "Not financial advice", "Tento týždeň", "Tento týden",
            "automated message", "automatická", "neodpovedaj")


@pytest.mark.parametrize("lang,subject_start,phrases", [
    ("de", "Diese Woche", ["Prognosen überprüft", "Wochenrückblick abbestellen", "Keine Anlageberatung",
                           "automatische Nachricht", 'lang="de"']),
    ("pl", "W tym tygodniu", ["sprawdzono", "Wypisz się", "To nie jest porada inwestycyjna",
                              "wiadomość automatyczna", 'lang="pl"']),
])
def test_digest_email_is_fully_translated(lang, subject_start, phrases):
    subject, text, html = digest.render_digest(User(id=7, username="x", lang=lang), _WEEK, _MINE)
    assert subject.startswith(subject_start)
    for phrase in phrases:
        assert phrase in html
    for leftover in _FOREIGN:
        assert leftover not in html and leftover not in text and leftover not in subject


@pytest.mark.parametrize("lang,expected,cta", [
    ("de", "Alarm: BTC liegt über $70,000", "AI Crypto Analytics öffnen"),
    ("pl", "Alert: BTC jest powyżej $70,000", "Otwórz AI Crypto Analytics"),
])
def test_alert_email_is_translated(lang, expected, cta):
    alert = PriceAlert(coin="BTC", kind="price", direction="above", target_price=70_000.0)
    text = alerts.describe(alert, 71_000.0, lang)
    assert text == expected
    subject, _text, html = alerts._email(User(id=1, username="x", lang=lang), text)
    assert subject == expected and cta in html and "Open AI Crypto Analytics" not in html
    move = PriceAlert(coin="ETH", kind="move", direction="below", target_price=5.0)
    assert "-6.0%" in alerts.describe(move, -6.0, lang)


@pytest.mark.parametrize("lang,title", [("de", "Guten Morgen!"), ("pl", "Dzień dobry!")])
def test_briefing_email_is_translated(lang, title):
    rows = [{"coin": "BTC", "price": 70_000.0, "target": 71_000.0, "change": 1.4, "low": 68_000.0, "high": 73_000.0}]
    market = [{"key": "funding", "tone": "bearish", "display": "+0.05%"}]
    subject, text, html = briefing.render_briefing(User(id=1, username="x", lang=lang), rows, market)
    assert title in text and title in html
    assert "Good morning" not in html and "Market signals" not in html and "Not financial advice" not in html


@pytest.mark.parametrize("lang", NEW_LANGS)
def test_code_and_login_emails_are_translated(lang):
    text, html = email_service.render_verification_email("anna", "123456", 15, lang)
    assert "123456" in text and "15" in text and "anna" in text
    assert "Welcome to AI Crypto Analytics" not in text and "valid for" not in html
    _text, html = email_service.render_new_login_email("anna", "now", "Firefox", "1.2.3.4", lang)
    assert "IP address" not in html and "Device" not in html


@pytest.mark.parametrize("lang", NEW_LANGS)
def test_demo_data_texts_are_translated(lang):
    for change in (3.0, -3.0, 0.0):
        text = demo_data._reasoning(lang, "Claude test", "BTC", "7D", 70_000.0, change, 65_000.0, 75_000.0, 2.5)
        assert "Test analysis" not in text and "Claude test" in text and "BTC" in text
    holdings, analysis = demo_data.build_portfolio(0, demo_data.DEMO_MODELS[0], lang)
    assert "Test analysis" not in analysis["odborna_analyza"]
    assert analysis["rebalancing_checklist"][0] != demo_data._CHECKLIST["en"][0]


@pytest.mark.parametrize("lang", NEW_LANGS)
def test_preferences_accept_de_and_pl(registered, lang):
    client, _username, _p = registered
    res = client.put("/api/account/preferences", json={"lang": lang}, headers=csrf_headers(client))
    assert res.status_code == 200, res.text
    assert res.json()["lang"] == lang


def test_preferences_still_reject_unknown_lang(registered):
    client, _username, _p = registered
    res = client.put("/api/account/preferences", json={"lang": "fr"}, headers=csrf_headers(client))
    assert res.status_code == 422
