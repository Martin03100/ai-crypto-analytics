"""
app/i18n_content.py
=====================
Preklady pre STATICKY/DEMONSTRACNY (mock) obsah generovany priamo backendom
(nie AI providerom) — napr. keď používateľ nemá pripojený API kľúč, alebo pre
zoznam nadchádzajúcich trhových udalostí. Skutočný text z AI providerov
(forecast/portfolio/news odôvodnenia pri pripojenom kľúči) sa NEPREKLADÁ —
ten prichádza priamo v jazyku promptu (viď app/services/validators.py).

Frontend posiela aktuálny jazyk UI (`lang`, jedna z "en"/"sk"/"cs") v tele
requestu pre všetky AI endpointy (viď frontend/src/api.js -> currentLang()).
Bez tejto hodnoty (napr. staršie Postman testy) sa použije "en" ako default.
"""

from __future__ import annotations

from typing import Dict, List

SUPPORTED_LANGS = ("en", "sk", "cs")
DEFAULT_LANG = "en"


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


# ---------------------------------------------------------------------------
# Jednotky pre casove body mock predikcie (naviazane na existujuce
# TIME_HORIZONS[...]["unit"] hodnoty v app/config.py — tie ostavaju ako
# interne identifikatory, tu sa iba prekladaju pre zobrazenie).
# ---------------------------------------------------------------------------
UNIT_LABELS: Dict[str, Dict[str, str]] = {
    "hodina": {"en": "hour", "sk": "hodina", "cs": "hodina"},
    "den": {"en": "day", "sk": "deň", "cs": "den"},
    "mesiac": {"en": "month", "sk": "mesiac", "cs": "měsíc"},
}


def unit_label(unit_key: str, lang: str) -> str:
    entry = UNIT_LABELS.get(unit_key, UNIT_LABELS["den"])
    return entry.get(normalize_lang(lang), entry[DEFAULT_LANG])


# ---------------------------------------------------------------------------
# "Chyba API kluc" — spolocna hlaska, ktora sprevadza VSETKY mock odpovede
# (forecast/portfolio/news/digest/chat), keď pouzivatel nema pripojeny kluc.
# ---------------------------------------------------------------------------
MISSING_API_KEY: Dict[str, str] = {
    "en": "Missing API key for the selected provider.",
    "sk": "Chýba API kľúč pre zvoleného providera.",
    "cs": "Chybí API klíč pro zvoleného providera.",
}


def missing_api_key_message(lang: str) -> str:
    return MISSING_API_KEY.get(normalize_lang(lang), MISSING_API_KEY[DEFAULT_LANG])


# ---------------------------------------------------------------------------
# Mock forecast (Forecast.jsx)
# ---------------------------------------------------------------------------
_TREND_WORDS: Dict[str, Dict[str, str]] = {
    "up": {"en": "rising", "sk": "rastúci", "cs": "rostoucí"},
    "down": {"en": "falling", "sk": "klesajúci", "cs": "klesající"},
}


def trend_word(direction: str, lang: str) -> str:
    return _TREND_WORDS[direction].get(normalize_lang(lang), _TREND_WORDS[direction][DEFAULT_LANG])


def mock_forecast_reasoning(coin: str, horizon: str, trend_direction: str, lang: str) -> str:
    lang = normalize_lang(lang)
    trend = trend_word(trend_direction, lang)
    templates = {
        "en": (
            f"[MOCK DATA] Simulated forecast for {coin} over {horizon} suggests a "
            f"{trend} trend based on a demonstration model. Connect a valid API key "
            f"in Account for a real AI analysis."
        ),
        "sk": (
            f"[MOCK DATA] Simulovaná predikcia pre {coin} na horizont {horizon} "
            f"naznačuje {trend} trend na základe demonštračného modelu. "
            f"Pripoj platný API kľúč v Účte pre reálnu AI analýzu."
        ),
        "cs": (
            f"[MOCK DATA] Simulovaná predikce pro {coin} na horizont {horizon} "
            f"naznačuje {trend} trend na základě demonstračního modelu. "
            f"Připoj platný API klíč v Účtu pro reálnou AI analýzu."
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


# ---------------------------------------------------------------------------
# Mock portfolio analysis (Portfolio.jsx)
# ---------------------------------------------------------------------------
def mock_portfolio_reason(action: str, coin: str, lang: str) -> str:
    lang = normalize_lang(lang)
    templates = {
        "en": {
            "BUY": f"[MOCK] {coin} shows a favorable technical structure for accumulating.",
            "SELL": f"[MOCK] {coin} looks overheated — consider a partial sell.",
            "HOLD": f"[MOCK] {coin} is in a stable range — holding is recommended.",
        },
        "sk": {
            "BUY": f"[MOCK] {coin} vykazuje priaznivú technickú štruktúru pre dokúpenie.",
            "SELL": f"[MOCK] {coin} sa javí prehriaty, zváž čiastočný predaj.",
            "HOLD": f"[MOCK] {coin} je v stabilnom pásme, odporúča sa držať.",
        },
        "cs": {
            "BUY": f"[MOCK] {coin} vykazuje příznivou technickou strukturu pro dokoupení.",
            "SELL": f"[MOCK] {coin} se jeví přehřátý, zvaž částečný prodej.",
            "HOLD": f"[MOCK] {coin} je ve stabilním pásmu, doporučuje se držet.",
        },
    }
    return templates.get(lang, templates[DEFAULT_LANG])[action]


MOCK_PORTFOLIO_ANALYSIS_TEXT: Dict[str, str] = {
    "en": (
        "[MOCK DATA] The portfolio could benefit from broader diversification "
        "across sectors such as RWA, L2 solutions and DeFi protocols. Consider "
        "reducing concentration in a single dominant position. Connect a valid "
        "API key for a real AI analysis."
    ),
    "sk": (
        "[MOCK DATA] Portfólio by mohlo profitovať zo širšej diverzifikácie "
        "naprieč sektormi ako RWA, L2 riešenia a DeFi protokoly. Zváž zníženie "
        "koncentrácie do jednej dominantnej pozície. Pripoj platný API kľúč "
        "pre reálnu AI analýzu."
    ),
    "cs": (
        "[MOCK DATA] Portfolio by mohlo profitovat ze širší diverzifikace "
        "napříč sektory jako RWA, L2 řešení a DeFi protokoly. Zvaž snížení "
        "koncentrace do jedné dominantní pozice. Připoj platný API klíč "
        "pro reálnou AI analýzu."
    ),
}

MOCK_REBALANCING_CHECKLIST: Dict[str, List[str]] = {
    "en": [
        "[MOCK] Check concentration in your largest position (recommended < 40%).",
        "[MOCK] Consider adding exposure to the DeFi sector.",
        "[MOCK] Set stop-loss levels for volatile positions.",
        "[MOCK] Review your portfolio every 2-4 weeks.",
    ],
    "sk": [
        "[MOCK] Skontroluj koncentráciu do najväčšej pozície (odporúčané < 40 %).",
        "[MOCK] Zváž pridanie expozície voči DeFi sektoru.",
        "[MOCK] Nastav si stop-loss úrovne pre volatilné pozície.",
        "[MOCK] Prehodnoť portfólio každé 2-4 týždne.",
    ],
    "cs": [
        "[MOCK] Zkontroluj koncentraci do největší pozice (doporučeno < 40 %).",
        "[MOCK] Zvaž přidání expozice vůči DeFi sektoru.",
        "[MOCK] Nastav si stop-loss úrovně pro volatilní pozice.",
        "[MOCK] Přehodnoť portfolio každé 2-4 týdny.",
    ],
}


# ---------------------------------------------------------------------------
# Mock news summary (Market.jsx)
# ---------------------------------------------------------------------------
MOCK_NEWS_TRENDS: Dict[str, List[str]] = {
    "en": [
        "[MOCK] Growing interest in L2 scaling solutions.",
        "[MOCK] Regulatory uncertainty is affecting altcoin sentiment.",
        "[MOCK] Institutional capital is shifting toward BTC/ETH.",
    ],
    "sk": [
        "[MOCK] Rastúci záujem o L2 škálovacie riešenia.",
        "[MOCK] Regulačná neistota ovplyvňuje sentiment altcoinov.",
        "[MOCK] Inštitucionálny kapitál sa presúva smerom k BTC/ETH.",
    ],
    "cs": [
        "[MOCK] Rostoucí zájem o L2 škálovací řešení.",
        "[MOCK] Regulační nejistota ovlivňuje sentiment altcoinů.",
        "[MOCK] Institucionální kapitál se přesouvá směrem k BTC/ETH.",
    ],
}


# ---------------------------------------------------------------------------
# Mock daily digest (DailyDigest.jsx)
# ---------------------------------------------------------------------------
def mock_digest_summary(fg_value: int, fg_classification: str, lang: str) -> str:
    lang = normalize_lang(lang)
    templates = {
        "en": (
            f"[MOCK DATA] The Fear & Greed Index is at {fg_value} today ({fg_classification}). "
            f"The market is currently in demo mode — connect a valid API key in "
            f"Account & API Keys for a real AI morning overview."
        ),
        "sk": (
            f"[MOCK DATA] Fear & Greed Index je dnes na {fg_value} ({fg_classification}). "
            f"Trh sa momentálne pohybuje v demonštračnom režime — pripoj platný API "
            f"kľúč v Účet & API kľúče pre reálny AI ranný prehľad."
        ),
        "cs": (
            f"[MOCK DATA] Fear & Greed Index je dnes na {fg_value} ({fg_classification}). "
            f"Trh se momentálně pohybuje v demonstračním režimu — připoj platný API "
            f"klíč v Účet & API klíče pro reálný AI ranní přehled."
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


MOCK_DIGEST_KEY_POINTS: Dict[str, List[str]] = {
    "en": [
        "[MOCK] Keep an eye on the Fear & Greed Index throughout the day.",
        "[MOCK] Check the latest headlines in the Market Sentiment section.",
        "[MOCK] Review your portfolio status in Portfolio Advisor.",
    ],
    "sk": [
        "[MOCK] Sleduj vývoj Fear & Greed Indexu počas dňa.",
        "[MOCK] Skontroluj najnovšie titulky v sekcii Trhový Sentiment.",
        "[MOCK] Over si stav svojho portfólia v Portfolio Advisor.",
    ],
    "cs": [
        "[MOCK] Sleduj vývoj Fear & Greed Indexu během dne.",
        "[MOCK] Zkontroluj nejnovější titulky v sekci Tržní Sentiment.",
        "[MOCK] Ověř si stav svého portfolia v Portfolio Advisor.",
    ],
}


# ---------------------------------------------------------------------------
# Mock chat reply (ChatWidget.jsx)
# ---------------------------------------------------------------------------
def mock_chat_reply(last_user_question: str, lang: str) -> str:
    lang = normalize_lang(lang)
    snippet = last_user_question[:120]
    templates = {
        "en": (
            "[MOCK DATA] I don't have an API key connected for the selected provider, "
            f"so this is a demo reply. Connect a valid key in Account & API Keys for a "
            f'real AI answer to: "{snippet}"'
        ),
        "sk": (
            "[MOCK DATA] Nemám pripojený API kľúč pre zvoleného providera, takže "
            f"odpovedám demonštračne. Pripoj platný kľúč v sekcii Účet & API kľúče "
            f'pre skutočnú AI odpoveď na otázku: "{snippet}"'
        ),
        "cs": (
            "[MOCK DATA] Nemám připojený API klíč pro zvoleného providera, takže "
            f"odpovídám demonstračně. Připoj platný klíč v sekci Účet & API klíče "
            f'pro skutečnou AI odpověď na otázku: "{snippet}"'
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


# ---------------------------------------------------------------------------
# Nadchadzajuce trhove udalosti (staticky demo obsah, Market.jsx)
# ---------------------------------------------------------------------------
MARKET_EVENTS_BY_LANG: Dict[str, List[Dict[str, object]]] = {
    "en": [
        {"offset_days": 3, "event": "FOMC meeting (interest rates)", "type": "Macro"},
        {"offset_days": 7, "event": "Ethereum network upgrade (testnet)", "type": "Network"},
        {"offset_days": 12, "event": "Inflation data release (CPI)", "type": "Macro"},
        {"offset_days": 18, "event": "Bitcoin halving anniversary / analysis", "type": "Network"},
        {"offset_days": 25, "event": "Crypto ETF decision", "type": "Regulatory"},
    ],
    "sk": [
        {"offset_days": 3, "event": "Zasadnutie FOMC (úrokové sadzby)", "type": "Makro"},
        {"offset_days": 7, "event": "Ethereum sieťový upgrade (testnet)", "type": "Sieťová"},
        {"offset_days": 12, "event": "Zverejnenie dát o inflácii (CPI)", "type": "Makro"},
        {"offset_days": 18, "event": "Bitcoin halving výročie / analýza", "type": "Sieťová"},
        {"offset_days": 25, "event": "Rozhodnutie o kryptomenovom ETF", "type": "Regulačná"},
    ],
    "cs": [
        {"offset_days": 3, "event": "Zasedání FOMC (úrokové sazby)", "type": "Makro"},
        {"offset_days": 7, "event": "Ethereum síťový upgrade (testnet)", "type": "Síťová"},
        {"offset_days": 12, "event": "Zveřejnění dat o inflaci (CPI)", "type": "Makro"},
        {"offset_days": 18, "event": "Bitcoin halving výročí / analýza", "type": "Síťová"},
        {"offset_days": 25, "event": "Rozhodnutí o kryptoměnovém ETF", "type": "Regulační"},
    ],
}


def market_events_for_lang(lang: str) -> List[Dict[str, object]]:
    return MARKET_EVENTS_BY_LANG.get(normalize_lang(lang), MARKET_EVENTS_BY_LANG[DEFAULT_LANG])
