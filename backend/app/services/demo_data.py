"""Synthetic test data for presentations (the "Load demo data" button).

Everything here is generated, clearly labelled and never mixed with real results:

* Prices are synthetic (seeded random walk with volatility clustering and market regimes), *not* real
  market prices. One hourly series per coin is shared by every forecast, so charts for the same coin are
  consistent with each other.
* Each test model ("Gemini test", "Claude test", ...) gets forecasts whose paths follow the shared price
  series with a model-specific skill, so they wiggle like real forecasts and are scored like real ones.
* Forecasts that have already matured are evaluated immediately (leaderboard, accuracy badges, price
  tips); the rest mature on the real clock.
* Demo rows are recognised by the model label suffix " test", which only this module writes (labels of
  real providers are fixed on the server), so the flag cannot be forged from the client. Demo evaluations
  are visible in the leaderboard only to the user who loaded them.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.config import DEFAULT_COIN_IDS, HORIZON_HOURS, SECTOR_CATEGORIES, TIME_HORIZONS
from app.i18n_content import _fmt_price, normalize_lang, unit_label
from app.models import ForecastEvaluation, ForecastHistory, PortfolioHistory, PriceTip
from app.services import quant_engine
from app.services.ai_engine import score_forecast

DEMO_LABEL_SUFFIX = " test"
DEMO_LABEL_LIKE = f"%{DEMO_LABEL_SUFFIX}"
DEMO_SOURCE = "demo_data"


def is_demo_label(model_used: Optional[str]) -> bool:
    return bool(model_used) and str(model_used).endswith(DEMO_LABEL_SUFFIX)


@dataclass(frozen=True)
class DemoModel:
    key: str
    label: str
    skill: float        # 0..1: how closely the forecast follows what the synthetic market really did
    bias: float         # >0 bullish, <0 bearish tendency
    confidence: Tuple[int, int]


DEMO_MODELS: Tuple[DemoModel, ...] = (
    DemoModel("anthropic", "Claude test", 0.34, 0.05, (68, 88)),
    DemoModel("gemini", "Gemini test", 0.30, 0.15, (62, 84)),
    DemoModel("openai", "OpenAI test", 0.26, 0.10, (60, 86)),
    DemoModel("deepseek", "DeepSeek test", 0.22, -0.10, (55, 80)),
    DemoModel("custom", "Custom model test", 0.18, 0.00, (52, 78)),
    DemoModel("grok", "Grok test", 0.12, 0.45, (50, 90)),
)

# coin -> (price "now", daily volatility, sector)
COINS: Dict[str, Tuple[float, float, str]] = {
    "BTC": (83_000.0, 0.023, "L1/L2"),
    "ETH": (2_650.0, 0.031, "L1/L2"),
    "SOL": (140.0, 0.043, "L1/L2"),
    "BNB": (610.0, 0.026, "Other"),
    "XRP": (2.3, 0.040, "Other"),
    "ADA": (0.70, 0.045, "L1/L2"),
    "DOGE": (0.17, 0.050, "Memes"),
    "AVAX": (24.0, 0.045, "L1/L2"),
    "DOT": (4.5, 0.045, "L1/L2"),
    "LINK": (15.0, 0.045, "DeFi"),
}
COIN_ORDER = list(COINS)

PAST_HOURS = 100 * 24            # history before "now" available to the model as market context
FUTURE_HOURS = 365 * 24          # pre-generated so pending forecasts mature consistently on the real clock
SERIES_LEN = PAST_HOURS + FUTURE_HOURS + 1
LOOKBACK_HOURS = 30 * 24         # volatility is estimated from the 30 days before a forecast
MAX_HOURS_AGO = PAST_HOURS - LOOKBACK_HOURS



def _floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


@lru_cache(maxsize=len(COINS))
def synthetic_series(coin: str) -> Tuple[float, ...]:
    """Hourly price series (immutable and cached: it depends only on the coin).
    Index PAST_HOURS is "now" and equals the coin's base price."""
    base, sigma_day, _sector = COINS[coin]
    rng = random.Random(f"demo-series|{coin}")
    sigma_h = sigma_day / math.sqrt(24)
    log_price = [0.0]
    vol, regime = 1.0, 0.0
    for i in range(1, SERIES_LEN):
        if i % 336 == 1:                       # a new market regime (trend) every two weeks
            regime = rng.gauss(0, 1)
        vol = math.exp(0.9 * math.log(vol) + 0.1 * rng.gauss(0, 0.35))   # volatility clustering
        pull = -0.0003 * log_price[-1]         # very slow mean reversion keeps prices in a sane range
        log_price.append(log_price[-1] + pull + regime * 0.06 * sigma_h + sigma_h * vol * rng.gauss(0, 1))
    anchor = log_price[PAST_HOURS]
    return tuple(base * math.exp(x - anchor) for x in log_price)


def _smooth(values: List[float]) -> List[float]:
    if len(values) < 3:
        return list(values)
    out = [values[0] * 0.75 + values[1] * 0.25]
    out += [0.25 * values[i - 1] + 0.5 * values[i] + 0.25 * values[i + 1] for i in range(1, len(values) - 1)]
    out.append(values[-1] * 0.75 + values[-2] * 0.25)
    return out


def _reasoning(lang: str, label: str, coin: str, horizon: str, spot: float, change_pct: float,
               low: float, high: float, sigma_day_pct: float) -> str:
    lang = normalize_lang(lang)
    tone = "up" if change_pct > 1.5 else "down" if change_pct < -1.5 else "flat"
    s, lo, hi = _fmt_price(spot), _fmt_price(low), _fmt_price(high)
    vol, chg = f"{sigma_day_pct:.1f}", f"{change_pct:+.1f}"
    texts = {
        "en": {
            "up": f"Test analysis by {label}: {coin} trades around ${s}. The model expects a rise of {chg}% by the end of the "
                  f"horizon ({horizon}), supported by positive momentum and daily volatility of {vol}%.",
            "down": f"Test analysis by {label}: {coin} trades around ${s}. The model expects a decline of {chg}% by the end of "
                    f"the horizon ({horizon}) as momentum weakens; daily volatility is {vol}%.",
            "flat": f"Test analysis by {label}: {coin} trades around ${s}. The model expects a sideways move ({chg}%) over the "
                    f"horizon ({horizon}) with daily volatility of {vol}%.",
            "tail": f"With 80% probability the price ends between ${lo} and ${hi}. Generated demo data on synthetic prices, not advice.",
        },
        "sk": {
            "up": f"Testovacia analýza modelu {label}: {coin} sa obchoduje okolo ${s}. Model očakáva rast o {chg} % do konca "
                  f"horizontu ({horizon}) vďaka pozitívnemu momentu a dennej volatilite {vol} %.",
            "down": f"Testovacia analýza modelu {label}: {coin} sa obchoduje okolo ${s}. Model očakáva pokles o {chg} % do konca "
                    f"horizontu ({horizon}) pri slabnúcom momente; denná volatilita je {vol} %.",
            "flat": f"Testovacia analýza modelu {label}: {coin} sa obchoduje okolo ${s}. Model očakáva bočný pohyb ({chg} %) "
                    f"počas horizontu ({horizon}) pri dennej volatilite {vol} %.",
            "tail": f"S 80 % pravdepodobnosťou skončí cena medzi ${lo} a ${hi}. Ide o vygenerované demo dáta zo syntetických cien, nie o radu.",
        },
        "cs": {
            "up": f"Testovací analýza modelu {label}: {coin} se obchoduje okolo ${s}. Model očekává růst o {chg} % do konce "
                  f"horizontu ({horizon}) díky pozitivnímu momentu a denní volatilitě {vol} %.",
            "down": f"Testovací analýza modelu {label}: {coin} se obchoduje okolo ${s}. Model očekává pokles o {chg} % do konce "
                    f"horizontu ({horizon}) při slábnoucím momentu; denní volatilita je {vol} %.",
            "flat": f"Testovací analýza modelu {label}: {coin} se obchoduje okolo ${s}. Model očekává boční pohyb ({chg} %) "
                    f"během horizontu ({horizon}) při denní volatilitě {vol} %.",
            "tail": f"S 80% pravděpodobností skončí cena mezi ${lo} a ${hi}. Jde o vygenerovaná demo data ze syntetických cen, ne o radu.",
        },
        "de": {
            "up": f"Testanalyse von {label}: {coin} notiert bei etwa ${s}. Das Modell erwartet bis zum Ende des Horizonts "
                  f"({horizon}) einen Anstieg um {chg} %, gestützt durch positives Momentum und eine tägliche Volatilität von {vol} %.",
            "down": f"Testanalyse von {label}: {coin} notiert bei etwa ${s}. Das Modell erwartet bis zum Ende des Horizonts "
                    f"({horizon}) einen Rückgang um {chg} %, da das Momentum nachlässt; die tägliche Volatilität liegt bei {vol} %.",
            "flat": f"Testanalyse von {label}: {coin} notiert bei etwa ${s}. Das Modell erwartet über den Horizont ({horizon}) "
                    f"eine Seitwärtsbewegung ({chg} %) bei einer täglichen Volatilität von {vol} %.",
            "tail": f"Mit 80 % Wahrscheinlichkeit endet der Preis zwischen ${lo} und ${hi}. Generierte Demodaten aus synthetischen Preisen, keine Beratung.",
        },
        "pl": {
            "up": f"Analiza testowa modelu {label}: {coin} jest notowany w okolicach ${s}. Model oczekuje wzrostu o {chg}% do końca "
                  f"horyzontu ({horizon}) dzięki pozytywnemu momentum i dziennej zmienności {vol}%.",
            "down": f"Analiza testowa modelu {label}: {coin} jest notowany w okolicach ${s}. Model oczekuje spadku o {chg}% do końca "
                    f"horyzontu ({horizon}) przy słabnącym momentum; dzienna zmienność wynosi {vol}%.",
            "flat": f"Analiza testowa modelu {label}: {coin} jest notowany w okolicach ${s}. Model oczekuje ruchu bocznego ({chg}%) "
                    f"w horyzoncie ({horizon}) przy dziennej zmienności {vol}%.",
            "tail": f"Z 80% prawdopodobieństwem cena zakończy się między ${lo} a ${hi}. To wygenerowane dane demo z syntetycznych cen, nie porada.",
        },
    }[lang]
    return f"{texts[tone]} {texts['tail']}"


def build_forecast(model: DemoModel, coin: str, horizon: str, hours_ago: int, series: Sequence[float],
                   base_time: datetime, lang: str) -> Dict[str, Any]:
    """One demo forecast created `hours_ago` hours before `base_time` (a whole hour)."""
    if not 0 <= hours_ago <= MAX_HOURS_AGO:
        raise ValueError("not enough synthetic history before the forecast")
    n = int(TIME_HORIZONS[horizon]["points"])
    total_hours = HORIZON_HOURS[horizon]
    created_idx = PAST_HOURS - hours_ago
    t0 = base_time - timedelta(hours=PAST_HOURS)
    spot = series[created_idx]
    created_at = t0 + timedelta(hours=created_idx)

    history = [[(t0 + timedelta(hours=i)).timestamp() * 1000, series[i]]
               for i in range(created_idx - LOOKBACK_HOURS, created_idx + 1)]
    sigma_h = quant_engine.estimate_sigma_per_hour(history) or (COINS[coin][1] / math.sqrt(24))
    step = quant_engine.STEP_HOURS[horizon]
    sigma_step = sigma_h * math.sqrt(step)

    actual = [series[created_idx + round(total_hours * (i + 1) / n)] for i in range(n)]
    truth = _smooth([math.log(a / spot) for a in actual])

    rng = random.Random(f"demo-forecast|{model.key}|{coin}|{horizon}|{hours_ago}")
    walk, acc = [], 0.0
    for _ in range(n):
        acc += rng.gauss(0, sigma_step)
        walk.append(acc)
    opinion = _smooth(walk)

    prices, wiggle = [], 0.0
    for i in range(n):
        wiggle = 0.5 * wiggle + rng.gauss(0, 0.35 * sigma_step)
        log_ret = (model.skill * truth[i] + (1 - model.skill) * opinion[i]
                   + model.bias * 0.12 * sigma_step * (i + 1) + wiggle)
        cap = 2.0 * sigma_step * math.sqrt(i + 1)
        prices.append(spot * math.exp(max(-cap, min(cap, log_ret))))

    sigma_day_pct = sigma_h * math.sqrt(24) * 100
    unit = unit_label(str(TIME_HORIZONS[horizon]["unit"]), lang)
    data: Dict[str, Any] = {
        "ceny": [quant_engine._fmt(p) for p in prices],
        "casove_body": [f"{unit} {i}" for i in range(1, n + 1)],
        "confidence_score": round(rng.uniform(*model.confidence), 1),
        "risk_level": "Low" if sigma_day_pct < 2.0 else "Medium" if sigma_day_pct < 4.5 else "High",
        "zdroje_dat": [DEMO_SOURCE],
        "aktualna_cena": quant_engine._fmt(spot),
        "vytvorene": created_at.isoformat(),
        "demo": True,
        "demo_actual": [quant_engine._fmt(a) for a in actual],
    }
    quant_engine.attach_uncertainty_band(data, history, horizon)   # adds "pasmo" + daily volatility
    band = data.get("pasmo") or {"dolne": data["ceny"], "horne": data["ceny"]}
    data["odovodnenie"] = _reasoning(lang, model.label, coin, horizon, spot, (data["ceny"][-1] / spot - 1) * 100,
                                     band["dolne"][-1], band["horne"][-1], sigma_day_pct)
    return data


def demo_accuracy(forecast_data: Dict[str, Any], created_at: datetime, timeframe: str,
                  now: Optional[datetime] = None) -> Dict[str, Any]:
    """Accuracy of a demo forecast from its stored synthetic outcome (no network); it is revealed only once
    the horizon has passed on the real clock, exactly like a real forecast."""
    now = now or datetime.now(timezone.utc)
    created_utc = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    matures = created_utc + timedelta(hours=HORIZON_HOURS.get(timeframe, 7 * 24))
    predicted = [float(p) for p in forecast_data.get("ceny", [])]
    labels = forecast_data.get("casove_body") if isinstance(forecast_data.get("casove_body"), list) else []
    base = {"predicted_prices": predicted, "time_labels": labels, "matures_at": matures.isoformat()}
    if now < matures:
        return {**base, "status": "pending", "accuracy_pct": None, "actual_prices": []}
    actual = [float(a) for a in forecast_data.get("demo_actual", [])]
    start = forecast_data.get("aktualna_cena")
    scored = score_forecast(predicted, actual, float(start)) if actual and isinstance(start, (int, float)) else None
    if scored is None:
        return {**base, "status": "unavailable", "accuracy_pct": None, "actual_prices": actual}
    return {**base, "status": "completed", "actual_prices": actual, **scored}


def _forecast_plan() -> List[Tuple[DemoModel, str, str, int]]:
    """(model, coin, horizon, hours_ago): six matured and three pending forecasts per model."""
    plan: List[Tuple[DemoModel, str, str, int]] = []
    for m, model in enumerate(DEMO_MODELS):
        def coin(k: int, offset: int = m * 3) -> str:
            return COIN_ORDER[(offset + k) % len(COIN_ORDER)]
        plan += [
            (model, coin(0), "1T", 24 * 40 + m * 5),
            (model, coin(1), "1T", 24 * 29 + m * 7),
            (model, coin(2), "1M", 24 * 60 + m * 3),
            (model, coin(3), "1T", 24 * 17 + m * 4),
            (model, coin(4), "24h", 24 * 9 + m * 2),
            (model, coin(5), "1T", 24 * 11 + m * 6),
            (model, coin(6), "1T", 24 * 2 + 4 + m),        # pending (created > 2 h ago, so no tipping window)
            (model, coin(7), "1M", 24 * 10 + m * 3),       # pending
            (model, coin(8), "24h", 5 + m),                # pending
        ]
    plan.append((DEMO_MODELS[1], "BTC", "1R", 24 * 45))     # a long-horizon forecast, pending for a while
    plan.append((DEMO_MODELS[0], "ETH", "1R", 24 * 50))
    return plan


# ---------------------------------------------------------------------------------------- portfolios

_REASONS = {
    "en": {"BUY": "{coin} makes up only {share}% of the portfolio and shows constructive momentum: room to add.",
           "SELL": "{coin} is {share}% of the portfolio and has run hot: consider trimming the position.",
           "SELL_SMALL": "{coin} is a small position ({share}%) with weakening momentum: consider closing it.",
           "HOLD": "{coin} ({share}% of the portfolio) is consolidating: holding the position is reasonable."},
    "sk": {"BUY": "{coin} tvorí len {share} % portfólia a vykazuje konštruktívny moment: je priestor na dokúpenie.",
           "SELL": "{coin} tvorí {share} % portfólia a je prehriaty: zváž zníženie pozície.",
           "SELL_SMALL": "{coin} je malá pozícia ({share} %) so slabnúcim momentom: zváž jej uzavretie.",
           "HOLD": "{coin} ({share} % portfólia) konsoliduje: držanie pozície je rozumné."},
    "cs": {"BUY": "{coin} tvoří jen {share} % portfolia a vykazuje konstruktivní moment: je prostor k dokoupení.",
           "SELL": "{coin} tvoří {share} % portfolia a je přehřátý: zvaž snížení pozice.",
           "SELL_SMALL": "{coin} je malá pozice ({share} %) se slábnoucím momentem: zvaž její uzavření.",
           "HOLD": "{coin} ({share} % portfolia) konsoliduje: držení pozice je rozumné."},
    "de": {"BUY": "{coin} macht nur {share} % des Portfolios aus und zeigt konstruktives Momentum: Raum zum Nachkaufen.",
           "SELL": "{coin} macht {share} % des Portfolios aus und ist heißgelaufen: überleg dir, die Position zu reduzieren.",
           "SELL_SMALL": "{coin} ist eine kleine Position ({share} %) mit nachlassendem Momentum: überleg dir, sie zu schließen.",
           "HOLD": "{coin} ({share} % des Portfolios) konsolidiert: die Position zu halten ist sinnvoll."},
    "pl": {"BUY": "{coin} stanowi tylko {share}% portfela i ma konstruktywne momentum: jest miejsce na dokupienie.",
           "SELL": "{coin} stanowi {share}% portfela i jest przegrzany: rozważ zmniejszenie pozycji.",
           "SELL_SMALL": "{coin} to mała pozycja ({share}%) ze słabnącym momentum: rozważ jej zamknięcie.",
           "HOLD": "{coin} ({share}% portfela) konsoliduje się: trzymanie pozycji jest rozsądne."},
}
_ANALYSIS = {
    "en": "Test analysis by {label}: the portfolio has {n} positions with total value of about ${total}. The largest position, "
          "{top}, is {top_share}% of the value{concentration}. Sector exposure is led by {sector}. Generated demo data, not advice.",
    "sk": "Testovacia analýza modelu {label}: portfólio má {n} pozícií s celkovou hodnotou približne ${total}. Najväčšia pozícia, "
          "{top}, tvorí {top_share} % hodnoty{concentration}. Sektorovej expozícii dominuje {sector}. Vygenerované demo dáta, nie rada.",
    "cs": "Testovací analýza modelu {label}: portfolio má {n} pozic s celkovou hodnotou přibližně ${total}. Největší pozice, "
          "{top}, tvoří {top_share} % hodnoty{concentration}. Sektorové expozici dominuje {sector}. Vygenerovaná demo data, ne rada.",
    "de": "Testanalyse von {label}: Das Portfolio hat {n} Positionen mit einem Gesamtwert von etwa ${total}. Die größte Position, "
          "{top}, macht {top_share} % des Werts aus{concentration}. Beim Sektor-Engagement führt {sector}. Generierte Demodaten, keine Beratung.",
    "pl": "Analiza testowa modelu {label}: portfel ma {n} pozycji o łącznej wartości około ${total}. Największa pozycja, "
          "{top}, stanowi {top_share}% wartości{concentration}. W ekspozycji sektorowej dominuje {sector}. Wygenerowane dane demo, nie porada.",
}
_CONCENTRATION = {"en": " - a high concentration", "sk": " - vysoká koncentrácia", "cs": " - vysoká koncentrace",
                  "de": " - eine hohe Konzentration", "pl": " - wysoka koncentracja"}
_CHECKLIST = {
    "en": ["Check concentration in your largest position ({top_share}%, recommended below 40%).",
           "Consider adding exposure to sectors you hold little of.",
           "Set stop-loss levels for the most volatile positions.",
           "Review the portfolio every 2-4 weeks."],
    "sk": ["Skontroluj koncentráciu v najväčšej pozícii ({top_share} %, odporúča sa pod 40 %).",
           "Zváž pridanie sektorov, ktorých máš málo.",
           "Nastav stop-loss pri najvolatilnejších pozíciách.",
           "Portfólio prehodnocuj každé 2-4 týždne."],
    "cs": ["Zkontroluj koncentraci v největší pozici ({top_share} %, doporučuje se pod 40 %).",
           "Zvaž přidání sektorů, kterých máš málo.",
           "Nastav stop-loss u nejvolatilnějších pozic.",
           "Portfolio přehodnocuj každé 2-4 týdny."],
    "de": ["Prüfe die Konzentration in deiner größten Position ({top_share} %, empfohlen unter 40 %).",
           "Überleg dir, Sektoren aufzunehmen, von denen du wenig hältst.",
           "Setz Stop-Loss-Marken für die volatilsten Positionen.",
           "Überprüfe das Portfolio alle 2-4 Wochen."],
    "pl": ["Sprawdź koncentrację w największej pozycji ({top_share}%, zalecane poniżej 40%).",
           "Rozważ dodanie sektorów, których masz mało.",
           "Ustaw stop-loss dla najbardziej zmiennych pozycji.",
           "Przeglądaj portfel co 2-4 tygodnie."],
}
PORTFOLIO_DAYS_AGO = (1, 3, 5, 8, 12, 17, 23, 30)


def build_portfolio(index: int, model: DemoModel, lang: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    lang = normalize_lang(lang)
    rng = random.Random(f"demo-portfolio|{index}")
    coins = rng.sample(COIN_ORDER, rng.randint(3, 6))
    total_target = rng.uniform(4_000, 45_000)
    weights = [rng.uniform(0.4, 3.0) ** 1.4 for _ in coins]
    holdings, values = [], {}
    for coin, weight in zip(coins, weights):
        amount = float(f"{total_target * weight / sum(weights) / COINS[coin][0]:.3g}")
        holdings.append({"minca": coin, "mnozstvo": amount, "coin_id": DEFAULT_COIN_IDS[coin]})
        values[coin] = amount * COINS[coin][0]
    total = sum(values.values())
    share = {c: v / total * 100 for c, v in values.items()}

    recommendations = []
    for coin in coins:
        if share[coin] > 40:
            action = "SELL" if rng.random() < 0.6 else "HOLD"
        else:
            action = rng.choices(["BUY", "HOLD", "SELL"], weights=[4, 4, 2])[0]
        # a large position is trimmed; a small one is closed - the wording must match its size
        reason_key = "SELL_SMALL" if action == "SELL" and share[coin] < 15 else action
        recommendations.append({"minca": coin, "akcia": action,
                                "dovod": _REASONS[lang][reason_key].format(coin=coin, share=f"{share[coin]:.0f}")})
    if len(recommendations) > 2 and all(r["akcia"] == "SELL" for r in recommendations):
        # an advisor that says "sell everything" is not a believable demo: keep the smallest position
        smallest = min(recommendations, key=lambda r: share[r["minca"]])
        smallest["akcia"] = "HOLD"
        smallest["dovod"] = _REASONS[lang]["HOLD"].format(coin=smallest["minca"], share=f"{share[smallest['minca']]:.0f}")

    sectors = {name: 0.0 for name in SECTOR_CATEGORIES}
    for coin, value in values.items():
        sectors[COINS[coin][2]] += value / total * 100
    sectors = {name: round(v, 1) for name, v in sectors.items()}
    top = max(share, key=share.get)
    top_sector = max(sectors, key=sectors.get)
    analysis = {
        "odporucania": recommendations,
        "odborna_analyza": _ANALYSIS[lang].format(
            label=model.label, n=len(coins), total=f"{total:,.0f}", top=top, top_share=f"{share[top]:.0f}",
            concentration=_CONCENTRATION[lang] if share[top] > 40 else "", sector=top_sector),
        "sektorova_alokacia": sectors,
        "rebalancing_checklist": [line.format(top_share=f"{share[top]:.0f}") for line in _CHECKLIST[lang]],
        "zdroje_dat": [DEMO_SOURCE],
        "demo": True,
    }
    return holdings, analysis


# ------------------------------------------------------------------------------------- create / remove

def remove_demo_data(db: Session, user_id: int) -> Dict[str, int]:
    ids = [row.id for row in db.query(ForecastHistory.id).filter(
        ForecastHistory.user_id == user_id, ForecastHistory.model_used.like(DEMO_LABEL_LIKE)).all()]
    if ids:
        db.query(ForecastEvaluation).filter(ForecastEvaluation.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(PriceTip).filter(PriceTip.forecast_id.in_(ids)).delete(synchronize_session=False)
        db.query(ForecastHistory).filter(ForecastHistory.id.in_(ids)).delete(synchronize_session=False)
    portfolios = db.query(PortfolioHistory).filter(
        PortfolioHistory.user_id == user_id, PortfolioHistory.model_used.like(DEMO_LABEL_LIKE)
    ).delete(synchronize_session=False)
    return {"forecasts": len(ids), "portfolios": portfolios}


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def create_demo_data(db: Session, user_id: int, lang: str = "en", now: Optional[datetime] = None) -> Dict[str, int]:
    """Replace the user's demo data with a fresh set. The caller commits."""
    now = now or datetime.now(timezone.utc)
    base_time = _floor_hour(now)
    remove_demo_data(db, user_id)

    created = {"forecasts": 0, "evaluations": 0, "tips": 0, "portfolios": 0}
    rows: List[Tuple[ForecastHistory, DemoModel, Dict[str, Any], str, str, int]] = []
    for model, coin, horizon, hours_ago in _forecast_plan():
        data = build_forecast(model, coin, horizon, hours_ago, synthetic_series(coin), base_time, lang)
        created_at = datetime.fromisoformat(data["vytvorene"])
        row = ForecastHistory(user_id=user_id, crypto_symbol=coin, timeframe=horizon, model_used=model.label,
                              forecast_json=json.dumps(data, ensure_ascii=False), created_at=_naive_utc(created_at))
        db.add(row)
        rows.append((row, model, data, coin, horizon, hours_ago))
    db.flush()   # assigns ids used by evaluations and tips
    created["forecasts"] = len(rows)

    for row, model, data, coin, horizon, hours_ago in rows:
        created_at = datetime.fromisoformat(data["vytvorene"])
        accuracy = demo_accuracy(data, created_at, horizon, now)
        if accuracy["status"] != "completed":
            continue
        db.add(ForecastEvaluation(
            forecast_id=row.id, user_id=user_id, provider=model.label, coin=coin, timeframe=horizon,
            accuracy_pct=accuracy["accuracy_pct"], baseline_accuracy_pct=accuracy["baseline_accuracy_pct"],
            direction_correct=bool(accuracy["direction_correct"]), actual_final_price=accuracy["actual_prices"][-1],
            evaluated_at=_naive_utc(created_at + timedelta(hours=HORIZON_HOURS[horizon])), is_demo=True))
        created["evaluations"] += 1
        tip_rng = random.Random(f"demo-tip|{model.key}|{coin}|{horizon}|{hours_ago}")
        if tip_rng.random() < 0.5:
            actual_final, ai_price = accuracy["actual_prices"][-1], accuracy["predicted_prices"][-1]
            ai_error_abs = abs(ai_price - actual_final)
            factor = math.exp(tip_rng.gauss(0.1, 0.6))     # the tip is about as good as the AI, a bit worse on average
            sign = 1 if tip_rng.random() < 0.5 else -1
            tip_price = quant_engine._fmt(max(actual_final * 0.01, actual_final + sign * ai_error_abs * factor))
            user_error, ai_error = abs(tip_price - actual_final), abs(ai_price - actual_final)
            outcome = "tie" if abs(user_error - ai_error) < 1e-9 else ("win" if user_error < ai_error else "loss")
            db.add(PriceTip(user_id=user_id, forecast_id=row.id, tip_price=tip_price, ai_price=ai_price,
                            outcome=outcome, created_at=_naive_utc(created_at + timedelta(minutes=30)), is_demo=True))
            created["tips"] += 1

    for index, days_ago in enumerate(PORTFOLIO_DAYS_AGO):
        model = DEMO_MODELS[index % len(DEMO_MODELS)]
        holdings, analysis = build_portfolio(index, model, lang)
        db.add(PortfolioHistory(
            user_id=user_id, holdings_json=json.dumps(holdings, ensure_ascii=False),
            analysis_json=json.dumps(analysis, ensure_ascii=False), model_used=model.label,
            created_at=_naive_utc(base_time - timedelta(days=days_ago, hours=index))))
        created["portfolios"] += 1
    return created
