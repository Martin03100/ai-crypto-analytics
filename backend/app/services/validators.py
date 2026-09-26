"""
app/services/validators.py
============================
Cistenie a bezpecne parsovanie JSON odpovedi z AI providerov, a
zostavovanie strictnych JSON-mode promptov. Ziadna funkcia tu nikdy
nevyhodi nezachytenu vynimku - safe_json_loads vzdy vracia predvidatelnu
(bool, dict|None, str|None) strukturu.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

FORECAST_REQUIRED_KEYS: Tuple[str, ...] = (
    "ceny", "casove_body", "odovodnenie", "confidence_score", "risk_level",
)
VALID_RISK_LEVELS: Tuple[str, ...] = ("Low", "Medium", "High")
PORTFOLIO_REQUIRED_KEYS: Tuple[str, ...] = (
    "odporucania", "odborna_analyza", "sektorova_alokacia", "rebalancing_checklist",
)
NEWS_REQUIRED_KEYS: Tuple[str, ...] = ("spravy", "trendy")
DIGEST_REQUIRED_KEYS: Tuple[str, ...] = ("zhrnutie", "kluceve_body")

# Spolocna instrukcia pre AI, aby nezohladnovala len historicke ceny, ale
# SIRSIU sadu realnych cenotvornych faktorov naprieč kryptotrhom - makro,
# regulacia, on-chain/derivatove trhove data, mainstreamove aj socialne
# medialne pokrytie, vyjadrenia vplyvnych osobnosti, a pri altcoinoch aj
# projektove fundamenty. LLM tu cerpa z vlastnych trenovacich dat (ziadny
# live web-search nie je k dispozicii pri volani provider API), takze ide
# o "odhad na zaklade vseobecnej znalosti kontextu", nie o realtime
# scraping - preto instrukcia explicitne ziada priznat, kde ide o predpoklad.
GLOBAL_CONTEXT_INSTRUCTION = (
    "Pri analyze NEBER do uvahy iba historicke cenove data. Zohladni siri "
    "kontext, ktory realne hyba kryptotrhom: "
    "(1) makroekonomiku a koreláciu s tradičnými trhmi - úrokové sadzby "
    "centrálnych bánk, infláciu, silu USD/DXY, pohyb akciových indexov "
    "(S&P 500, Nasdaq) a zlata; "
    "(2) reguláciu a geopolitiku - rozhodnutia regulátorov, súdne spory, "
    "sankcie, napätie medzi štátmi; "
    "(3) krypto-špecifické trhové dáta - tok prostriedkov na/z búrz, pohyby "
    "veľkých peňaženiek (whale), prítoky/odtoky ETF fondov, funding rates a "
    "open interest na derivátoch; "
    "(4) médiá a sentiment - mainstreamové finančné spravodajstvo AJ nálada "
    "na sociálnych sieťach (X/Twitter, Reddit, Telegram) a v krypto "
    "komunitách/fórach, vrátane rozlíšenia, či ide o širší medializovaný "
    "názor alebo len o lokálnu bublinu nadšenia/paniky; "
    "(5) verejné vyjadrenia vplyvných osobností - zakladatelia projektov, "
    "inštitucionálni investori, regulátori; "
    "(6) pri konkrétnych projektoch (nie BTC/ETH) aj ich vlastné fundamenty "
    "- token unlocks, partnerstvá, technologické míľniky; "
    "(7) klimatické a energetické vplyvy relevantné pre mining/staking. "
    "Faktory, ku ktorým nemáš aktuálne dáta, nepredstieraj - ale ani ich "
    "nevypisuj ako zoznam chýbajúcich dát; ak to podstatne znižuje istotu, "
    "stačí jedna krátka zmienka."
)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?", re.IGNORECASE)


def strip_markdown_fences(raw_text: str) -> str:
    if not raw_text:
        return ""
    return _MARKDOWN_FENCE_PATTERN.sub("", raw_text).strip()


def extract_json_object(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None
    cleaned = strip_markdown_fences(raw_text)
    match = _JSON_BLOCK_PATTERN.search(cleaned)
    return match.group(0) if match else None


def safe_json_loads(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    candidate = extract_json_object(raw_text)
    if candidate is None:
        return False, None, "V odpovedi sa nepodarilo najst ziadny JSON objekt."
    try:
        data = json.loads(candidate)
        if not isinstance(data, dict):
            return False, None, "Naparsovany JSON nie je objekt (dict)."
        return True, data, None
    except json.JSONDecodeError as exc:
        return False, None, f"Chyba pri parsovani JSON: {exc}"


def _missing_keys(data: Dict[str, Any], required: Tuple[str, ...]) -> List[str]:
    return [key for key in required if key not in data]


def validate_forecast_payload(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    success, data, error = safe_json_loads(raw_text)
    if not success or data is None:
        return False, None, error
    missing = _missing_keys(data, FORECAST_REQUIRED_KEYS)
    if missing:
        return False, None, f"Chybajuce kluce: {', '.join(missing)}"
    if not isinstance(data.get("ceny"), list) or not data["ceny"]:
        return False, None, "Pole 'ceny' musi byt neprazdny zoznam cisel."
    if not isinstance(data.get("casove_body"), list) or not data["casove_body"]:
        return False, None, "Pole 'casove_body' musi byt neprazdny zoznam."
    if len(data["ceny"]) != len(data["casove_body"]):
        return False, None, "Polia 'ceny' a 'casove_body' musia mat rovnaku dlzku."
    if not isinstance(data.get("odovodnenie"), str) or not data["odovodnenie"].strip():
        return False, None, "Pole 'odovodnenie' musi byt neprazdny text."
    score = data.get("confidence_score")
    if not isinstance(score, (int, float)) or not (0 <= float(score) <= 100):
        return False, None, "Pole 'confidence_score' musi byt cislo 0-100."
    risk = data.get("risk_level")
    if risk not in VALID_RISK_LEVELS:
        return False, None, f"Pole 'risk_level' musi byt jedno z: {', '.join(VALID_RISK_LEVELS)}."
    return True, data, None


def validate_portfolio_payload(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    success, data, error = safe_json_loads(raw_text)
    if not success or data is None:
        return False, None, error
    missing = _missing_keys(data, PORTFOLIO_REQUIRED_KEYS)
    if missing:
        return False, None, f"Chybajuce kluce: {', '.join(missing)}"
    recommendations = data.get("odporucania")
    if not isinstance(recommendations, list) or not recommendations:
        return False, None, "Pole 'odporucania' musi byt neprazdny zoznam."
    for i, item in enumerate(recommendations):
        if not isinstance(item, dict):
            return False, None, f"Odporucanie na indexe {i} nie je objekt."
        item_missing = _missing_keys(item, ("minca", "akcia", "dovod"))
        if item_missing:
            return False, None, f"Odporucanie {i} nema kluce: {', '.join(item_missing)}"
    if not isinstance(data.get("sektorova_alokacia"), dict) or not data["sektorova_alokacia"]:
        return False, None, "Pole 'sektorova_alokacia' musi byt neprazdny objekt."
    if not isinstance(data.get("rebalancing_checklist"), list) or not data["rebalancing_checklist"]:
        return False, None, "Pole 'rebalancing_checklist' musi byt neprazdny zoznam."
    if not isinstance(data.get("odborna_analyza"), str) or not data["odborna_analyza"].strip():
        return False, None, "Pole 'odborna_analyza' musi byt neprazdny text."
    return True, data, None


def validate_news_payload(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    success, data, error = safe_json_loads(raw_text)
    if not success or data is None:
        return False, None, error
    missing = _missing_keys(data, NEWS_REQUIRED_KEYS)
    if missing:
        return False, None, f"Chybajuce kluce: {', '.join(missing)}"
    if not isinstance(data.get("spravy"), list) or not data["spravy"]:
        return False, None, "Pole 'spravy' musi byt neprazdny zoznam."
    if not isinstance(data.get("trendy"), list) or not data["trendy"]:
        return False, None, "Pole 'trendy' musi byt neprazdny zoznam."
    return True, data, None


def validate_digest_payload(raw_text: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    success, data, error = safe_json_loads(raw_text)
    if not success or data is None:
        return False, None, error
    missing = _missing_keys(data, DIGEST_REQUIRED_KEYS)
    if missing:
        return False, None, f"Chybajuce kluce: {', '.join(missing)}"
    if not isinstance(data.get("zhrnutie"), str) or not data["zhrnutie"].strip():
        return False, None, "Pole 'zhrnutie' musi byt neprazdny text."
    if not isinstance(data.get("kluceve_body"), list) or not data["kluceve_body"]:
        return False, None, "Pole 'kluceve_body' musi byt neprazdny zoznam."
    return True, data, None


def build_daily_digest_prompt(fear_greed_value: int, fear_greed_classification: str, headlines: List[str]) -> str:
    headlines_text = "\n".join(f"- {title}" for title in headlines[:6])
    return (
        f"Si krypto trhovy analytik pripravujuci rychle ranne zhrnutie pre "
        f"investora. Fear & Greed Index je dnes {fear_greed_value} "
        f"({fear_greed_classification}). Dnesne titulky:\n{headlines_text}\n\n"
        f"{GLOBAL_CONTEXT_INSTRUCTION} "
        f"Naps zhrnutie v 3-4 vetach a 3-5 klucovych bodov na sledovanie dnes. "
        f"Odpovedz VYHRADNE ako platny JSON bez markdown obalu, bez sprievodneho "
        f"textu, presne v tomto tvare:\n"
        f'{{"zhrnutie": "/* 3-4 vety rannej analyzy trhu */", '
        f'"kluceve_body": ["/* bod 1 */", "/* bod 2 */", "..."]}}'
    )


_HORIZON_STEP = {"24h": "hodinu", "1T": "den", "1M": "den", "1R": "mesiac"}


def build_forecast_prompt(coin: str, horizon: str, points: int, market_context: str | None = None) -> str:
    context_block = (
        f"SKUTOCNE aktualne trhove data pre {coin} (pouzi ako hlavny zaklad predikcie): {market_context}. "
        if market_context else
        f"Aktualne trhove data pre {coin} nie su k dispozicii - vychadzaj zo vseobecnych znalosti o tomto aktive, "
        f"ale jasne to zohladni v nizsej istote (confidence_score) a v odovodneni to spomen. "
    )
    return (
        f"Si expert na kryptomenovu analyzu. {context_block}"
        f"Predikcia MUSI vychadzat z poskytnuteho trendu (24h/7d zmena), NIE zo vseobecneho predpokladu, "
        f"ze kryptomeny dlhodobo rastu - ak trend klesa alebo je neisty, predikuj pokles/stagnaciu rovnako "
        f"ochotne ako rast. Falosny optimizmus je horsi ako priznana neistota. "
        f"Prvy bod predikcie musi nadvazovat na aktualnu cenu a celkovy pohyb drz v realistickom rozsahu "
        f"podla uvedenej dennej volatility, pokial data nedavaju silny dovod na vacsi pohyb. "
        f"Vytvor cenovu predikciu pre kryptomenu {coin} na casovy horizont {horizon} s presne {points} "
        f"datovymi bodmi. Casovanie: bod c. 1 je cena o 1 {_HORIZON_STEP.get(horizon, 'jednotku casu')} od TERAZ, dalsie body "
        f"idu po rovnakych krokoch a posledny bod je cena na konci horizontu. {GLOBAL_CONTEXT_INSTRUCTION} "
        f"Odpovedz VYHRADNE ako platny JSON bez markdown obalu, "
        f"bez sprievodneho textu, presne v tomto tvare:\n"
        f'{{"ceny": [/* {points} cisel (float) */], '
        f'"casove_body": [/* {points} textovych popiskov casu */], '
        f'"odovodnenie": "/* strucne slovne zdovodnenie predikcie, vratane '
        f'spomenutia relevantneho makro/geopoliticke/sentiment kontextu a aktualneho trendu */", '
        f'"confidence_score": /* cislo 0-100, ako vela si isty predikciou */, '
        f'"risk_level": "/* presne jedno z: Low, Medium, High */"}}'
    )


def build_portfolio_prompt(holdings: List[Dict[str, Any]], market_context: str | None = None) -> str:
    holdings_text = ", ".join(f"{item.get('minca', '?')}: {item.get('mnozstvo', 0)}" for item in holdings)
    context_block = (
        f"SKUTOCNE aktualne trhove data (pouzi ako hlavny zaklad analyzy; hodnoty a vahy pozicii su presne "
        f"vypocitane): {market_context}. " if market_context else ""
    )
    return (
        f"Si profesionalny krypto investicny poradca, ktory hodnoti kazdu poziciu striktne na zaklade jej "
        f"vlastnych rizik a fundamentov - nie automaticky ako BUY. Analyzuj portfolio: "
        f"{holdings_text}. {context_block}Zameraj sa na rizika, diverzifikaciu a sektorove "
        f"zlozenie (DeFi, L1/L2, AI, Memes, Other). {GLOBAL_CONTEXT_INSTRUCTION} "
        f"DOLEZITE: pouzivaj SELL a HOLD rovnako casto ako BUY, ked si to riziko/koncentracia/volatilita danej "
        f"pozicie realisticky vyzaduje - odporucanie BUY pre kazdu poziciu by bolo nezodpovedne a nerealisticke. "
        f"Odpovedz VYHRADNE ako "
        f"platny JSON bez markdown obalu, bez sprievodneho textu, presne v tomto tvare:\n"
        f'{{"odporucania": [{{"minca": str, "akcia": "BUY|SELL|HOLD", "dovod": str}}, ...], '
        f'"odborna_analyza": "/* komentar k rizikam, diverzifikacii a sirsiemu trhovemu kontextu */", '
        f'"sektorova_alokacia": {{"DeFi": float, "L1/L2": float, "AI": float, "Memes": float, "Other": float}}, '
        f'"rebalancing_checklist": ["/* krok 1 */", "/* krok 2 */", "..."]}}'
    )


def build_news_prompt(headlines: List[str]) -> str:
    headlines_text = "\n".join(f"- {title}" for title in headlines)
    return (
        f"Si krypto trhovy analytik. Nizsie je zoznam dnesnych titulkov sprav:\n"
        f"{headlines_text}\n\n"
        f"Pre kazdy titulok urci sentiment (Bullish/Bearish/Neutral) a zostav "
        f"zoznam 3-5 aktualnych trhovych meta-trendov. {GLOBAL_CONTEXT_INSTRUCTION} "
        f"Odpovedz VYHRADNE ako "
        f"platny JSON bez markdown obalu, bez sprievodneho textu, presne v tomto tvare:\n"
        f'{{"spravy": [{{"titulok": str, "sentiment": "Bullish|Bearish|Neutral"}}, ...], '
        f'"trendy": ["/* trend 1 */", "/* trend 2 */", "..."]}}'
    )


_LANGUAGE_NAMES = {
    "en": "English",
    "sk": "slovenčina (spisovná, s diakritikou)",
    "cz": "čeština (spisovná, s diakritikou)",
    "cs": "čeština (spisovná, s diakritikou)",
}


def language_instruction(lang: str, json_mode: bool = True) -> str:
    """Prompty su po slovensky - bez tejto instrukcie AI odpovedala po
    slovensky aj anglickym/ceskym pouzivatelom (a obcas bez diakritiky)."""
    name = _LANGUAGE_NAMES.get((lang or "en").lower(), _LANGUAGE_NAMES["en"])
    if json_mode:
        return f"\nVsetky TEXTOVE hodnoty v JSON odpovedi napis v jazyku: {name}. Kluce JSON nemen."
    return f"\nOdpovedz v jazyku: {name}."
