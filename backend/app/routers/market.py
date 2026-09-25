"""app/routers/market.py — Fear&Greed, news sentiment, udalosti, community poll."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    RATE_LIMIT_AI_ENDPOINT, RATE_LIMIT_MARKET_PUBLIC, RATE_LIMIT_VOTE,
)
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import CommunityVote, User
from app.rate_limit import rate_limit_by_ip, rate_limit_by_user
from app.schemas import AIResultOut, DailyDigestRequest, VoteRequest
from app.services.ai_engine import get_daily_digest, get_news_sentiment_summary
from app.services.market_data import (
    get_crypto_headlines, get_dummy_crypto_headlines, get_dummy_fear_greed_index,
    get_fear_greed_index, get_live_prices, get_market_chart, get_upcoming_market_events, search_coins,
)

router = APIRouter(prefix="/api/market", tags=["market"])

VALID_VOTES = ("Bullish", "Neutral", "Bearish")


@router.get("/fear-greed", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def fear_greed(refresh: bool = False) -> dict:
    success, data, error = get_fear_greed_index(force_refresh=refresh)
    if not success or data is None:
        return {"data": get_dummy_fear_greed_index(), "is_mock": True, "error_message": error}
    return {"data": data, "is_mock": False, "error_message": None}


@router.get("/headlines")
def headlines() -> dict:
    success, items, error = get_crypto_headlines(limit=8)
    if not success or not items:
        return {"headlines": get_dummy_crypto_headlines(limit=6), "is_mock": True, "error_message": error}
    return {"headlines": items, "is_mock": False, "error_message": None}


@router.post("/news-sentiment", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def news_sentiment(payload: dict, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> AIResultOut:
    provider = payload.get("provider")
    titles: List[str] = payload.get("titles", [])
    lang = payload.get("lang", "en")
    api_key = get_decrypted_api_key(db, user.id, provider) if provider else None
    result = get_news_sentiment_summary(provider, titles, api_key, lang)
    return AIResultOut(**result.as_dict())


@router.get("/prices", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def prices(ids: str, vs_currency: str = "usd") -> dict:
    """Live ceny z CoinGecko (cachovane 60s). `ids` je ciarkou oddeleny
    zoznam CoinGecko id, napr. 'bitcoin,ethereum'. `vs_currency` urcuje
    menu (usd/eur/czk/btc) podla zvolenej primarnej meny v Nastaveniach.
    Rate-limitovane podla IP (nie je to autentifikovany endpoint) - inak by
    mohol jeden pouzivatel spamom vycerpat bezplatny CoinGecko rate limit
    a znefunkcnit ceny pre vsetkych ostatnych."""
    coin_ids = [c.strip() for c in ids.split(",") if c.strip()]
    success, data, error = get_live_prices(coin_ids, vs_currency)
    if not success or data is None:
        return {"prices": {}, "is_mock": True, "error_message": error}
    return {"prices": data, "is_mock": False, "error_message": error}


@router.get("/chart", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def chart(coin_id: str = "bitcoin", vs_currency: str = "usd", days: str = "7") -> dict:
    """Historicke ceny pre interaktivny graf (zoom + prepinanie timeframu)."""
    success, data, error = get_market_chart(coin_id, vs_currency, days)
    return {"prices": data, "is_mock": not success, "error_message": error}


@router.get("/coins/search", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
def coins_search(q: str) -> dict:
    success, results, error = search_coins(q)
    return {"results": results, "error_message": error if not success else None}


@router.post("/daily-digest", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_AI_ENDPOINT))])
def daily_digest(payload: DailyDigestRequest, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> AIResultOut:
    """Rychle AI zhrnutie trhu pre otvorenie appky (Daily Digest)."""
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    fg_success, fg_data, _ = get_fear_greed_index()
    fg_value = fg_data["value"] if fg_success and fg_data else 50
    fg_classification = fg_data["classification"] if fg_success and fg_data else "Neutral"

    news_success, headlines_raw, _ = get_crypto_headlines(limit=6)
    headlines = [h["title"] for h in headlines_raw] if news_success else []

    result = get_daily_digest(payload.provider, fg_value, fg_classification, headlines, api_key, payload.lang)
    return AIResultOut(**result.as_dict())


@router.get("/events", dependencies=[Depends(rate_limit_by_ip(*RATE_LIMIT_MARKET_PUBLIC))])
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
    """Percentualne rozlozenie POSLEDNEHO hlasu kazdeho pouzivatela.

    Pocitane priamo v SQL (namiesto nacitania vsetkych riadkov CommunityVote
    do pamate a spracovania v Pythone) - skaluje sa aj pri velkom pocte
    hlasov, lebo databaza robi agregaciu, nie aplikacny server."""
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
