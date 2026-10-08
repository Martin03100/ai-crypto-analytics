"""Localized backend texts (EN, SK, CS, DE, PL)."""

from __future__ import annotations

from typing import Dict, List, Tuple

SUPPORTED_LANGS = ("en", "sk", "cs", "de", "pl")
DEFAULT_LANG = "en"


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


UNIT_LABELS: Dict[str, Dict[str, str]] = {
    "hodina": {"en": "hour", "sk": "hodina", "cs": "hodina", "de": "Stunde", "pl": "godzina"},
    "den": {"en": "day", "sk": "deň", "cs": "den", "de": "Tag", "pl": "dzień"},
    "mesiac": {"en": "month", "sk": "mesiac", "cs": "měsíc", "de": "Monat", "pl": "miesiąc"},
}


def unit_label(unit_key: str, lang: str) -> str:
    entry = UNIT_LABELS.get(unit_key, UNIT_LABELS["den"])
    return entry.get(normalize_lang(lang), entry[DEFAULT_LANG])


MISSING_API_KEY: Dict[str, str] = {
    "en": "Missing API key for the selected provider.",
    "sk": "Chýba API kľúč pre zvoleného providera.",
    "cs": "Chybí API klíč pro zvoleného providera.",
    "de": "Für den gewählten Anbieter fehlt der API-Schlüssel.",
    "pl": "Brakuje klucza API dla wybranego dostawcy.",
}


def missing_api_key_message(lang: str) -> str:
    return MISSING_API_KEY.get(normalize_lang(lang), MISSING_API_KEY[DEFAULT_LANG])


_TREND_WORDS: Dict[str, Dict[str, str]] = {
    "up": {"en": "rising", "sk": "rastúci", "cs": "rostoucí", "de": "steigenden", "pl": "wzrostowy"},
    "down": {"en": "falling", "sk": "klesajúci", "cs": "klesající", "de": "fallenden", "pl": "spadkowy"},
}


def trend_word(direction: str, lang: str) -> str:
    return _TREND_WORDS[direction].get(normalize_lang(lang), _TREND_WORDS[direction][DEFAULT_LANG])


def mock_forecast_reasoning(coin: str, horizon: str, trend_direction: str, lang: str) -> str:
    lang = normalize_lang(lang)
    trend = trend_word(trend_direction, lang)
    templates = {
        "en": (
            f"[SAMPLE DATA] Simulated forecast for {coin} over {horizon} suggests a "
            f"{trend} trend based on a demonstration model. Connect a valid API key "
            f"in Account for a real AI analysis."
        ),
        "sk": (
            f"[UKÁŽKOVÉ DÁTA] Simulovaná predikcia pre {coin} na horizont {horizon} "
            f"naznačuje {trend} trend na základe demonštračného modelu. "
            f"Pripoj platný API kľúč v Účte pre reálnu AI analýzu."
        ),
        "cs": (
            f"[UKÁZKOVÁ DATA] Simulovaná predikce pro {coin} na horizont {horizon} "
            f"naznačuje {trend} trend na základě demonstračního modelu. "
            f"Připoj platný API klíč v Účtu pro reálnou AI analýzu."
        ),
        "de": (
            f"[BEISPIELDATEN] Die simulierte Prognose für {coin} über {horizon} deutet auf einen "
            f"{trend} Trend hin, basierend auf einem Demo-Modell. Hinterlege einen gültigen API-Schlüssel "
            f"im Konto für eine echte KI-Analyse."
        ),
        "pl": (
            f"[DANE PRZYKŁADOWE] Symulowana prognoza dla {coin} na horyzont {horizon} "
            f"wskazuje na trend {trend} na podstawie modelu demonstracyjnego. "
            f"Podłącz ważny klucz API w Koncie, aby otrzymać prawdziwą analizę AI."
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


def _fmt_price(value: float) -> str:
    return f"{value:,.2f}" if value >= 1 else f"{value:.6g}"


def quant_reasoning(lang: str, coin: str, horizon: str, sigma_day_pct: float, change_pct: float,
                    low: float, high: float, spot: float) -> str:
    lang = normalize_lang(lang)
    lo, hi, now = _fmt_price(low), _fmt_price(high), _fmt_price(spot)
    templates = {
        "en": (
            f"Free statistical model (no AI): {coin} at ${now}, horizon {horizon}. Typical daily volatility over "
            f"the last 30 days is {sigma_day_pct:.1f}%. The median path moves {change_pct:+.1f}% (momentum is "
            f"deliberately damped - short-term crypto trends are unreliable). With 80% probability the price at "
            f"the end of the horizon lands between ${lo} and ${hi}. This is a reference estimate, not advice."
        ),
        "sk": (
            f"Bezplatný štatistický model (bez AI): {coin} za ${now}, horizont {horizon}. Typická denná volatilita "
            f"za posledných 30 dní je {sigma_day_pct:.1f} %. Stredná trajektória sa pohybuje o {change_pct:+.1f} % "
            f"(momentum je zámerne utlmené - krátkodobé trendy na kryptotrhu sú nespoľahlivé). S 80 % "
            f"pravdepodobnosťou skončí cena na konci horizontu medzi ${lo} a ${hi}. Ide o referenčný odhad, nie o radu."
        ),
        "cs": (
            f"Bezplatný statistický model (bez AI): {coin} za ${now}, horizont {horizon}. Typická denní volatilita "
            f"za posledních 30 dní je {sigma_day_pct:.1f} %. Střední trajektorie se pohybuje o {change_pct:+.1f} % "
            f"(momentum je záměrně utlumeno - krátkodobé trendy na kryptotrhu jsou nespolehlivé). S 80% "
            f"pravděpodobností skončí cena na konci horizontu mezi ${lo} a ${hi}. Jde o referenční odhad, ne o radu."
        ),
        "de": (
            f"Kostenloses statistisches Modell (ohne KI): {coin} bei ${now}, Horizont {horizon}. Die typische tägliche "
            f"Volatilität der letzten 30 Tage liegt bei {sigma_day_pct:.1f} %. Der Medianpfad bewegt sich um {change_pct:+.1f} % "
            f"(das Momentum ist bewusst gedämpft - kurzfristige Krypto-Trends sind unzuverlässig). Mit 80 % "
            f"Wahrscheinlichkeit liegt der Preis am Ende des Horizonts zwischen ${lo} und ${hi}. Das ist eine Richtschätzung, keine Beratung."
        ),
        "pl": (
            f"Darmowy model statystyczny (bez AI): {coin} po ${now}, horyzont {horizon}. Typowa dzienna zmienność "
            f"z ostatnich 30 dni wynosi {sigma_day_pct:.1f}%. Mediana ścieżki zmienia się o {change_pct:+.1f}% "
            f"(momentum jest celowo wytłumione - krótkoterminowe trendy na rynku krypto są niewiarygodne). Z 80% "
            f"prawdopodobieństwem cena na końcu horyzontu znajdzie się między ${lo} a ${hi}. To szacunek orientacyjny, nie porada."
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


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
        "de": {
            "BUY": f"[MOCK] {coin} zeigt eine günstige technische Struktur zum Nachkaufen.",
            "SELL": f"[MOCK] {coin} wirkt überhitzt, überleg dir einen Teilverkauf.",
            "HOLD": f"[MOCK] {coin} bewegt sich in einer stabilen Spanne, Halten wird empfohlen.",
        },
        "pl": {
            "BUY": f"[MOCK] {coin} ma korzystną strukturę techniczną do dokupienia.",
            "SELL": f"[MOCK] {coin} wygląda na przegrzany, rozważ częściową sprzedaż.",
            "HOLD": f"[MOCK] {coin} jest w stabilnym przedziale, zalecane jest trzymanie.",
        },
    }
    return templates.get(lang, templates[DEFAULT_LANG])[action]


MOCK_PORTFOLIO_ANALYSIS_TEXT: Dict[str, str] = {
    "en": (
        "[SAMPLE DATA] The portfolio could benefit from broader diversification "
        "across sectors such as RWA, L2 solutions and DeFi protocols. Consider "
        "reducing concentration in a single dominant position. Connect a valid "
        "API key for a real AI analysis."
    ),
    "sk": (
        "[UKÁŽKOVÉ DÁTA] Portfólio by mohlo profitovať zo širšej diverzifikácie "
        "naprieč sektormi ako RWA, L2 riešenia a DeFi protokoly. Zváž zníženie "
        "koncentrácie do jednej dominantnej pozície. Pripoj platný API kľúč "
        "pre reálnu AI analýzu."
    ),
    "cs": (
        "[UKÁZKOVÁ DATA] Portfolio by mohlo profitovat ze širší diverzifikace "
        "napříč sektory jako RWA, L2 řešení a DeFi protokoly. Zvaž snížení "
        "koncentrace do jedné dominantní pozice. Připoj platný API klíč "
        "pro reálnou AI analýzu."
    ),
    "de": (
        "[BEISPIELDATEN] Das Portfolio könnte von einer breiteren Diversifikation "
        "über Sektoren wie RWA, L2-Lösungen und DeFi-Protokolle profitieren. Überleg dir, "
        "die Konzentration auf eine einzelne dominante Position zu verringern. Hinterlege einen "
        "gültigen API-Schlüssel für eine echte KI-Analyse."
    ),
    "pl": (
        "[DANE PRZYKŁADOWE] Portfel mógłby skorzystać na szerszej dywersyfikacji "
        "w sektorach takich jak RWA, rozwiązania L2 i protokoły DeFi. Rozważ zmniejszenie "
        "koncentracji w jednej dominującej pozycji. Podłącz ważny klucz API, "
        "aby otrzymać prawdziwą analizę AI."
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
    "de": [
        "[MOCK] Prüfe die Konzentration in deiner größten Position (empfohlen < 40 %).",
        "[MOCK] Überleg dir, Engagement im DeFi-Sektor aufzubauen.",
        "[MOCK] Setz Stop-Loss-Marken für volatile Positionen.",
        "[MOCK] Überprüfe dein Portfolio alle 2-4 Wochen.",
    ],
    "pl": [
        "[MOCK] Sprawdź koncentrację w swojej największej pozycji (zalecane < 40%).",
        "[MOCK] Rozważ zwiększenie ekspozycji na sektor DeFi.",
        "[MOCK] Ustaw poziomy stop-loss dla zmiennych pozycji.",
        "[MOCK] Przeglądaj portfel co 2-4 tygodnie.",
    ],
}


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
    "de": [
        "[MOCK] Wachsendes Interesse an L2-Skalierungslösungen.",
        "[MOCK] Regulatorische Unsicherheit belastet die Stimmung bei Altcoins.",
        "[MOCK] Institutionelles Kapital verlagert sich in Richtung BTC/ETH.",
    ],
    "pl": [
        "[MOCK] Rosnące zainteresowanie rozwiązaniami skalującymi L2.",
        "[MOCK] Niepewność regulacyjna wpływa na sentyment wobec altcoinów.",
        "[MOCK] Kapitał instytucjonalny przesuwa się w stronę BTC/ETH.",
    ],
}


def mock_digest_summary(fg_value: int, fg_classification: str, lang: str) -> str:
    lang = normalize_lang(lang)
    templates = {
        "en": (
            f"[SAMPLE DATA] The Fear & Greed Index is at {fg_value} today ({fg_classification}). "
            f"The market is currently in demo mode — connect a valid API key in "
            f"Account & API Keys for a real AI morning overview."
        ),
        "sk": (
            f"[UKÁŽKOVÉ DÁTA] Fear & Greed Index je dnes na {fg_value} ({fg_classification}). "
            f"Trh sa momentálne pohybuje v demonštračnom režime — pripoj platný API "
            f"kľúč v Účet & API kľúče pre reálny AI ranný prehľad."
        ),
        "cs": (
            f"[UKÁZKOVÁ DATA] Fear & Greed Index je dnes na {fg_value} ({fg_classification}). "
            f"Trh se momentálně pohybuje v demonstračním režimu — připoj platný API "
            f"klíč v Účet & API klíče pro reálný AI ranní přehled."
        ),
        "de": (
            f"[BEISPIELDATEN] Der Fear & Greed Index steht heute bei {fg_value} ({fg_classification}). "
            f"Der Markt läuft gerade im Demo-Modus — hinterlege einen gültigen API-Schlüssel unter "
            f"Konto & API-Schlüssel für einen echten KI-Morgenüberblick."
        ),
        "pl": (
            f"[DANE PRZYKŁADOWE] Fear & Greed Index wynosi dziś {fg_value} ({fg_classification}). "
            f"Rynek działa obecnie w trybie demonstracyjnym — podłącz ważny klucz API "
            f"w sekcji Konto i klucze API, aby otrzymać prawdziwy poranny przegląd AI."
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
    "de": [
        "[MOCK] Behalte den Fear & Greed Index im Laufe des Tages im Blick.",
        "[MOCK] Sieh dir die neuesten Schlagzeilen im Bereich Marktstimmung an.",
        "[MOCK] Prüfe den Stand deines Portfolios im Portfolio Advisor.",
    ],
    "pl": [
        "[MOCK] Śledź Fear & Greed Index w ciągu dnia.",
        "[MOCK] Sprawdź najnowsze nagłówki w sekcji Sentyment rynku.",
        "[MOCK] Sprawdź stan swojego portfela w Portfolio Advisor.",
    ],
}


def mock_chat_reply(last_user_question: str, lang: str) -> str:
    lang = normalize_lang(lang)
    snippet = last_user_question[:120]
    templates = {
        "en": (
            "[SAMPLE DATA] I don't have an API key connected for the selected provider, "
            f"so this is a demo reply. Connect a valid key in Account & API Keys for a "
            f'real AI answer to: "{snippet}"'
        ),
        "sk": (
            "[UKÁŽKOVÉ DÁTA] Nemám pripojený API kľúč pre zvoleného providera, takže "
            f"odpovedám demonštračne. Pripoj platný kľúč v sekcii Účet & API kľúče "
            f'pre skutočnú AI odpoveď na otázku: "{snippet}"'
        ),
        "cs": (
            "[UKÁZKOVÁ DATA] Nemám připojený API klíč pro zvoleného providera, takže "
            f"odpovídám demonstračně. Připoj platný klíč v sekci Účet & API klíče "
            f'pro skutečnou AI odpověď na otázku: "{snippet}"'
        ),
        "de": (
            "[BEISPIELDATEN] Für den gewählten Anbieter ist kein API-Schlüssel hinterlegt, "
            f"daher ist das eine Demo-Antwort. Hinterlege einen gültigen Schlüssel unter Konto & API-Schlüssel "
            f'für eine echte KI-Antwort auf: "{snippet}"'
        ),
        "pl": (
            "[DANE PRZYKŁADOWE] Nie mam podłączonego klucza API dla wybranego dostawcy, "
            f"więc to odpowiedź demonstracyjna. Podłącz ważny klucz w sekcji Konto i klucze API, "
            f'aby otrzymać prawdziwą odpowiedź AI na pytanie: "{snippet}"'
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


# Real, officially published dates (decision day of each FOMC meeting, CPI release day).
# Sources: federalreserve.gov/monetarypolicy/fomccalendars.htm, bls.gov/schedule/news_release/cpi.htm
# BLS publishes next year's CPI schedule in autumn - extend the list when it is out.
MARKET_EVENT_CALENDAR: List[Tuple[str, str]] = [
    ("2026-01-28", "fomc"), ("2026-03-18", "fomc"), ("2026-04-29", "fomc"), ("2026-06-17", "fomc"),
    ("2026-07-29", "fomc"), ("2026-09-16", "fomc"), ("2026-10-28", "fomc"), ("2026-12-09", "fomc"),
    ("2027-01-27", "fomc"), ("2027-03-17", "fomc"), ("2027-04-28", "fomc"), ("2027-06-09", "fomc"),
    ("2027-07-28", "fomc"), ("2027-09-15", "fomc"), ("2027-10-27", "fomc"), ("2027-12-08", "fomc"),
    ("2026-01-13", "cpi"), ("2026-02-13", "cpi"), ("2026-03-11", "cpi"), ("2026-04-10", "cpi"),
    ("2026-05-12", "cpi"), ("2026-06-10", "cpi"), ("2026-07-14", "cpi"), ("2026-08-12", "cpi"),
    ("2026-09-11", "cpi"), ("2026-10-14", "cpi"), ("2026-11-10", "cpi"), ("2026-12-10", "cpi"),
]

MARKET_EVENT_LABELS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "en": {"fomc": ("FOMC interest rate decision (Fed)", "Macro"),
           "cpi": ("US inflation data release (CPI)", "Macro")},
    "sk": {"fomc": ("Rozhodnutie FOMC o úrokových sadzbách (Fed)", "Makro"),
           "cpi": ("Zverejnenie dát o inflácii v USA (CPI)", "Makro")},
    "cs": {"fomc": ("Rozhodnutí FOMC o úrokových sazbách (Fed)", "Makro"),
           "cpi": ("Zveřejnění dat o inflaci v USA (CPI)", "Makro")},
    "de": {"fomc": ("FOMC-Zinsentscheid (Fed)", "Makro"),
           "cpi": ("Veröffentlichung der US-Inflationsdaten (CPI)", "Makro")},
    "pl": {"fomc": ("Decyzja FOMC w sprawie stóp procentowych (Fed)", "Makro"),
           "cpi": ("Publikacja danych o inflacji w USA (CPI)", "Makro")},
}


def market_events_for_lang(lang: str) -> Dict[str, Tuple[str, str]]:
    return MARKET_EVENT_LABELS.get(normalize_lang(lang), MARKET_EVENT_LABELS[DEFAULT_LANG])
