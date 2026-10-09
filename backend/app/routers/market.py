"""Market API."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    DEFAULT_COIN_IDS,
    RATE_LIMIT_AI_ENDPOINT, RATE_LIMIT_MARKET_GLOBAL, RATE_LIMIT_MARKET_PUBLIC, RATE_LIMIT_VOTE,
)
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import CommunityVote, User
from app.rate_limit import rate_limit_by_ip, rate_limit_by_user, rate_limit_global
from app.schemas import AIResultOut, DailyDigestRequest, NewsSentimentRequest, VoteRequest
from app.services import jobs, signals
from app.services.ai_engine import get_daily_digest, get_news_sentiment_summary
from app.services.market_data import (
    VALID_CHART_DAYS, VALID_VS_CURRENCIES, is_valid_coin_id,
    get_crypto_headlines, get_fear_greed_index, get_live_prices, get_market_chart, get_upcoming_market_events, search_coins,
)

router = APIRouter(prefix="/api/market", tags=["market"])

VALID_VOTES = ("Bullish", "Neutral", "Bearish")
_PUBLIC_LIMITS = [Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC)), Depends(rate_limit_global("market", *RATE_LIMIT_MARKET_GLOBAL))]


def _check_vs_currency(value: str) -> str:
    value = (value or "usd").lower()
    if value not in VALID_VS_CURRENCIES:
        raise HTTPException(status_code=400, detail="Nepodporovaná mena (usd, eur, czk, btc).")
    return value


# When a source is down the app says so ("could not load, try again") instead of showing an invented value.

@router.get("/fear-greed", dependencies=_PUBLIC_LIMITS)
def fear_greed(refresh: bool = False) -> dict:
    success, data, error = get_fear_greed_index(force_refresh=refresh)
    if not success or data is None:
        return {"data": None, "is_mock": False, "error_message": error}
    return {"data": data, "is_mock": False, "error_message": None}


@router.get("/headlines", dependencies=_PUBLIC_LIMITS)
def headlines() -> dict:
    success, items, error = get_crypto_headlines(limit=8)
    if not success or not items:
        return {"headlines": [], "is_mock": False, "error_message": error or "unavailable"}
    return {"headlines": items, "is_mock": False, "error_message": None}


@router.post("/news-sentiment", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def news_sentiment(payload: NewsSentimentRequest, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    provider = payload.provider
    titles: List[str] = [title[:300] for title in payload.titles]
    lang = payload.lang
    api_key = get_decrypted_api_key(db, user.id, provider) if provider else None
    return jobs.respond(request, user.id, lambda: AIResultOut(
        **get_news_sentiment_summary(provider, titles, api_key, lang).as_dict()).model_dump())


@router.get("/prices", dependencies=_PUBLIC_LIMITS)
def prices(ids: str, vs_currency: str = "usd") -> dict:
    vs_currency = _check_vs_currency(vs_currency)
    coin_ids = [c.strip() for c in ids.split(",") if c.strip()][:50]
    if not all(is_valid_coin_id(c) for c in coin_ids):
        raise HTTPException(status_code=400, detail="Neplatné ID mince.")
    success, data, error = get_live_prices(coin_ids, vs_currency)
    if not success or data is None:
        return {"prices": {}, "is_mock": True, "error_message": error}
    return {"prices": data, "is_mock": False, "error_message": error}


@router.get("/chart", dependencies=_PUBLIC_LIMITS)
def chart(coin_id: str = "bitcoin", vs_currency: str = "usd", days: str = "7") -> dict:
    vs_currency = _check_vs_currency(vs_currency)
    if not is_valid_coin_id(coin_id):
        raise HTTPException(status_code=400, detail="Neplatné ID mince.")
    if days not in VALID_CHART_DAYS:
        raise HTTPException(status_code=400, detail="Nepodporované obdobie grafu.")
    success, data, error = get_market_chart(coin_id, vs_currency, days)
    return {"prices": data, "is_mock": not success, "error_message": error}


@router.get("/coins/search", dependencies=_PUBLIC_LIMITS)
def coins_search(q: str) -> dict:
    q = (q or "")[:60]
    success, results, error = search_coins(q)
    return {"results": results, "error_message": error if not success else None}


@router.post("/daily-digest", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def daily_digest(payload: DailyDigestRequest, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    return jobs.respond(request, user.id, lambda: _daily_digest(payload, api_key))


def _daily_digest(payload: DailyDigestRequest, api_key) -> dict:
    fg_success, fg_data, _ = get_fear_greed_index()
    fg_value = fg_data["value"] if fg_success and fg_data else None         # unknown, never a made-up 50
    fg_classification = fg_data["classification"] if fg_success and fg_data else None

    news_success, headlines_raw, _ = get_crypto_headlines(limit=6)
    headlines = [h["title"] for h in headlines_raw] if news_success else []

    result = get_daily_digest(payload.provider, fg_value, fg_classification, headlines, api_key, payload.lang)
    return AIResultOut(**result.as_dict()).model_dump()


@router.get("/signals", dependencies=_PUBLIC_LIMITS)
def market_signals(coin: str = Query(default="BTC", max_length=10), lang: str = Query(default="en", max_length=5)) -> dict:
    """Derivatives, options, flows, macro and more for one coin (market-wide parts are shared)."""
    coin = coin.upper()
    if coin not in DEFAULT_COIN_IDS:
        raise HTTPException(status_code=400, detail="Táto minca nie je podporovaná.")
    bundle = signals.collect(coin)
    items = [{k: v for k, v in s.items() if k != "note"} for s in bundle["items"] if s["key"] != "event"]
    items += [{k: v for k, v in s.items() if k != "note"} for s in signals.events(lang=lang)]   # names in the UI language
    items.sort(key=lambda s: signals.GROUPS.index(s["group"]))
    return {"coin": coin, "items": items, "sources": bundle["sources"], "updated_at": bundle["updated_at"],
            "score": signals.score(items)}


@router.get("/events", dependencies=_PUBLIC_LIMITS)
def events(lang: str = "en") -> dict:
    return {"events": get_upcoming_market_events(lang)}


@router.post("/vote", dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_VOTE))])
def add_vote(payload: VoteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.sentiment_vote not in VALID_VOTES:
        return {"success": False, "message": "Neplatna hodnota hlasu."}
    db.add(CommunityVote(user_id=user.id, sentiment_vote=payload.sentiment_vote))
    db.commit()
    return {"success": True}


@router.get("/vote/mine")
def my_vote(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.query(CommunityVote).filter(CommunityVote.user_id == user.id).order_by(
        CommunityVote.voted_at.desc()
    ).first()
    return {"sentiment_vote": row.sentiment_vote if row else None}


@router.get("/vote/percentages")
def vote_percentages(db: Session = Depends(get_db)) -> dict:
    latest_per_user = (
        db.query(CommunityVote.user_id, func.max(CommunityVote.voted_at).label("max_voted_at"))
        .group_by(CommunityVote.user_id)
        .subquery()
    )
    rows = (
        db.query(CommunityVote.sentiment_vote, func.count().label("cnt"))
        .join(
            latest_per_user,
            (CommunityVote.user_id == latest_per_user.c.user_id)
            & (CommunityVote.voted_at == latest_per_user.c.max_voted_at),
        )
        .group_by(CommunityVote.sentiment_vote)
        .all()
    )
    counts = {v: 0 for v in VALID_VOTES}
    for sentiment_vote, cnt in rows:
        if sentiment_vote in counts:
            counts[sentiment_vote] = cnt

    total = sum(counts.values())
    percentages = {vote: (0.0 if total == 0 else round((count / total) * 100, 1)) for vote, count in counts.items()}
    percentages["total_votes"] = total
    return percentages



@router.get("/onchain", dependencies=_PUBLIC_LIMITS)
def onchain_overview() -> dict:
    import time as _time
    from concurrent.futures import ThreadPoolExecutor

    from app.services import data_sources

    coins = (("BTC", "bitcoin"), ("ETH", "ethereum"), ("DOGE", "dogecoin"))
    pool = ThreadPoolExecutor(max_workers=len(coins))
    try:
        futures = [(symbol, pool.submit(data_sources.onchain_stats, coin_id)) for symbol, coin_id in coins]
        deadline = _time.monotonic() + 6
        items = []
        for symbol, future in futures:
            try:
                stats = future.result(timeout=max(0.1, deadline - _time.monotonic()))
            except Exception:  # noqa: BLE001
                stats = None
            if stats:
                items.append({"coin": symbol, **stats})
        return {"items": items}
    finally:
        pool.shutdown(wait=False)
