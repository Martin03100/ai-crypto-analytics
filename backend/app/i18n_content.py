"""Localized backend texts (EN, SK, CS, DE, PL)."""

from __future__ import annotations

import math
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


HORIZON_NAMES: Dict[str, Dict[str, str]] = {
    "en": {"4h": "4 hours", "24h": "24 hours", "1T": "1 week", "1M": "1 month", "1R": "1 year"},
    "sk": {"4h": "4 hodiny", "24h": "24 hodín", "1T": "1 týždeň", "1M": "1 mesiac", "1R": "1 rok"},
    "cs": {"4h": "4 hodiny", "24h": "24 hodin", "1T": "1 týden", "1M": "1 měsíc", "1R": "1 rok"},
    "de": {"4h": "4 Stunden", "24h": "24 Stunden", "1T": "1 Woche", "1M": "1 Monat", "1R": "1 Jahr"},
    "pl": {"4h": "4 godziny", "24h": "24 godziny", "1T": "1 tydzień", "1M": "1 miesiąc", "1R": "1 rok"},
}


def horizon_name(horizon: str, lang: str) -> str:
    return HORIZON_NAMES[normalize_lang(lang)].get(horizon, horizon)


_NBSP = "\u00a0"     # keeps "81 761,42 $" on one line


def _localize_number(text: str, lang: str) -> str:
    """English digits "81,761.42" in the reader's style: 81 761,42 (sk, cs, pl) or 81.761,42 (de)."""
    if lang == "en":
        return text
    thousands = "." if lang == "de" else _NBSP
    return text.replace(",", "|").replace(".", ",").replace("|", thousands)


def _fmt_price(value: float) -> str:
    """English-style price digits; small coins (PEPE, SHIB) get three significant digits, never 1.05e-05."""
    if value >= 1:
        return f"{value:,.2f}"
    decimals = min(12, max(2, 2 - math.floor(math.log10(value)))) if value > 0 else 2
    return f"{value:.{decimals}f}"


def fmt_money(value: float, lang: str) -> str:
    lang = normalize_lang(lang)
    digits = _localize_number(_fmt_price(value), lang)
    return f"${digits}" if lang == "en" else f"{digits}{_NBSP}$"


def fmt_pct(value: float, lang: str, signed: bool = False) -> str:
    lang = normalize_lang(lang)
    digits = _localize_number(f"{value:+.1f}" if signed else f"{value:.1f}", lang)
    return f"{digits}%" if lang in ("en", "pl") else f"{digits}{_NBSP}%"


def quant_reasoning(lang: str, coin: str, horizon: str, sigma_day_pct: float, change_pct: float,
                    low: float, high: float, spot: float) -> str:
    lang = normalize_lang(lang)
    lo, hi, now = fmt_money(low, lang), fmt_money(high, lang), fmt_money(spot, lang)
    vol, move, h = fmt_pct(sigma_day_pct, lang), fmt_pct(change_pct, lang, signed=True), horizon_name(horizon, lang)
    templates = {
        "en": (
            f"Free statistical model (no AI): {coin} at {now}, horizon {h}. Typical daily volatility over "
            f"the last 30 days is {vol}. The median path moves {move} (momentum is "
            f"deliberately damped - short-term crypto trends are unreliable). With 80% probability the price at "
            f"the end of the horizon lands between {lo} and {hi}. This is a reference estimate, not advice."
        ),
        "sk": (
            f"Bezplatný štatistický model (bez AI): {coin} za {now}, horizont {h}. Typická denná volatilita "
            f"za posledných 30 dní je {vol}. Stredná trajektória sa pohybuje o {move} "
            f"(momentum je zámerne utlmené - krátkodobé trendy na kryptotrhu sú nespoľahlivé). S 80 % "
            f"pravdepodobnosťou skončí cena na konci horizontu medzi {lo} a {hi}. Ide o referenčný odhad, nie o radu."
        ),
        "cs": (
            f"Bezplatný statistický model (bez AI): {coin} za {now}, horizont {h}. Typická denní volatilita "
            f"za posledních 30 dní je {vol}. Střední trajektorie se pohybuje o {move} "
            f"(momentum je záměrně utlumeno - krátkodobé trendy na kryptotrhu jsou nespolehlivé). S 80% "
            f"pravděpodobností skončí cena na konci horizontu mezi {lo} a {hi}. Jde o referenční odhad, ne o radu."
        ),
        "de": (
            f"Kostenloses statistisches Modell (ohne KI): {coin} bei {now}, Horizont {h}. Die typische tägliche "
            f"Volatilität der letzten 30 Tage liegt bei {vol}. Der Medianpfad bewegt sich um {move} "
            f"(das Momentum ist bewusst gedämpft - kurzfristige Krypto-Trends sind unzuverlässig). Mit 80 % "
            f"Wahrscheinlichkeit liegt der Preis am Ende des Horizonts zwischen {lo} und {hi}. Das ist eine Richtschätzung, keine Beratung."
        ),
        "pl": (
            f"Darmowy model statystyczny (bez AI): {coin} po {now}, horyzont {h}. Typowa dzienna zmienność "
            f"z ostatnich 30 dni wynosi {vol}. Mediana ścieżki zmienia się o {move} "
            f"(momentum jest celowo wytłumione - krótkoterminowe trendy na rynku krypto są niewiarygodne). Z 80% "
            f"prawdopodobieństwem cena na końcu horyzontu znajdzie się między {lo} a {hi}. To szacunek orientacyjny, nie porada."
        ),
    }
    return templates.get(lang, templates[DEFAULT_LANG])


def sample_portfolio_reason(coin: str, lang: str) -> str:
    """Sample analysis without an AI key: says plainly that nothing was assessed (no invented advice)."""
    lang = normalize_lang(lang)
    templates = {
        "en": f"[MOCK] Sample only: {coin} was not assessed. Connect an AI key for a real analysis.",
        "sk": f"[MOCK] Len ukážka: {coin} nebol posúdený. Pre skutočnú analýzu pripoj AI kľúč.",
        "cs": f"[MOCK] Jen ukázka: {coin} nebyl posouzen. Pro skutečnou analýzu připoj AI klíč.",
        "de": f"[MOCK] Nur ein Beispiel: {coin} wurde nicht bewertet. Für eine echte Analyse hinterlege einen KI-Schlüssel.",
        "pl": f"[MOCK] Tylko przykład: {coin} nie został oceniony. Podłącz klucz AI, aby otrzymać prawdziwą analizę.",
    }
    return templates.get(lang, templates[DEFAULT_LANG])


MOCK_PORTFOLIO_ANALYSIS_TEXT: Dict[str, str] = {
    "en": "[SAMPLE DATA] This is only a sample: your portfolio was not analysed. The sector split below is simply "
          "the number of coins per sector. Connect an AI key in Account & API keys for a real look at risks and diversification.",
    "sk": "[UKÁŽKOVÉ DÁTA] Toto je len ukážka: tvoje portfólio nebolo analyzované. Rozdelenie podľa sektorov nižšie "
          "je len počet mincí v každom sektore. Pre skutočný pohľad na riziká a diverzifikáciu pripoj AI kľúč v Účet & API kľúče.",
    "cs": "[UKÁZKOVÁ DATA] Toto je jen ukázka: tvoje portfolio nebylo analyzováno. Rozdělení podle sektorů níže "
          "je jen počet mincí v každém sektoru. Pro skutečný pohled na rizika a diverzifikaci připoj AI klíč v Účet & API klíče.",
    "de": "[BEISPIELDATEN] Das ist nur ein Beispiel: dein Portfolio wurde nicht analysiert. Die Sektorverteilung unten "
          "zählt nur die Coins pro Sektor. Für einen echten Blick auf Risiken und Diversifikation hinterlege einen KI-Schlüssel unter Konto & API-Schlüssel.",
    "pl": "[DANE PRZYKŁADOWE] To tylko przykład: twój portfel nie został przeanalizowany. Podział na sektory poniżej "
          "to tylko liczba monet w każdym sektorze. Aby zobaczyć prawdziwe ryzyka i dywersyfikację, podłącz klucz AI w sekcji Konto i klucze API.",
}

MOCK_REBALANCING_CHECKLIST: Dict[str, List[str]] = {
    "en": ["[MOCK] Connect an AI key to get a checklist for your own portfolio."],
    "sk": ["[MOCK] Pripoj AI kľúč a dostaneš kontrolný zoznam pre svoje portfólio."],
    "cs": ["[MOCK] Připoj AI klíč a dostaneš kontrolní seznam pro své portfolio."],
    "de": ["[MOCK] Hinterlege einen KI-Schlüssel, um eine Checkliste für dein eigenes Portfolio zu bekommen."],
    "pl": ["[MOCK] Podłącz klucz AI, aby otrzymać listę kontrolną dla swojego portfela."],
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
