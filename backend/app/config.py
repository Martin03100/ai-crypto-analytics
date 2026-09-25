"""
app/config.py
==============
Globalne nastavenia, konstanty, API endpointy a bezpecnostne parametre
pre cely backend. Nic ine by nemalo obsahovat hardcoded providerov,
URL alebo tabulkove nazvy - vsetko sa importuje odtialto.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Final, List

# ---------------------------------------------------------------------------
# Vseobecne
# ---------------------------------------------------------------------------
APP_TITLE: Final[str] = "AI Crypto Analytics"
REQUEST_TIMEOUT_SECONDS: Final[int] = 12

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
DB_PATH: Final[Path] = DATA_DIR / "app.db"
# V produkcii mozes nastavit DATABASE_URL (napr. na hostovanu Postgres DB -
# Render/Neon/Supabase a pod.), aby data prezili restart/redeploy servera
# (viac v DEPLOYMENT.md). Bez tejto env premennej appka pouziva lokalny
# SQLite subor ako doteraz - spravanie pre lokalny vyvoj sa nemeni.
DATABASE_URL: Final[str] = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

# ---------------------------------------------------------------------------
# Bezpecnost - JWT a sifrovanie API klucov (AES-256 / Fernet)
# ---------------------------------------------------------------------------
# V produkcii NAČÍTAŤ z env premennych. Fallback iba pre lokalny vyvoj.
JWT_SECRET_KEY: Final[str] = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me-in-production")
JWT_ALGORITHM: Final[str] = "HS256"
JWT_EXPIRE_MINUTES: Final[int] = 60 * 24 * 7  # 7 dni

# ---------------------------------------------------------------------------
# HttpOnly auth cookie (nahradzuje ulozenie JWT v localStorage kvoli XSS)
# ---------------------------------------------------------------------------
AUTH_COOKIE_NAME: Final[str] = "aca_session"
AUTH_COOKIE_MAX_AGE_SECONDS: Final[int] = JWT_EXPIRE_MINUTES * 60
# V produkcii (APP_ENV=production) sa cookie posiela iba cez HTTPS.
APP_ENV: Final[str] = os.environ.get("APP_ENV", "development")
AUTH_COOKIE_SECURE: Final[bool] = APP_ENV == "production"
AUTH_COOKIE_SAMESITE: Final[str] = "lax"

# Fernet kluc (32 url-safe base64 bytes) pre sifrovanie API klucov v DB.
# V produkcii NAČÍTAŤ z env / secret manazera (napr. AWS KMS, Vault).
API_KEY_ENCRYPTION_SECRET: Final[str] = os.environ.get(
    "API_KEY_ENCRYPTION_SECRET", "dev-fernet-key-change-me-in-production-32b"
)

# ---------------------------------------------------------------------------
# AI provideri
# ---------------------------------------------------------------------------
PROVIDERS: Final[Dict[str, str]] = {
    "Gemini": "gemini",
    "OpenAI (ChatGPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "DeepSeek": "deepseek",
    "Grok (xAI)": "grok",
}
PROVIDER_LABELS: Final[Dict[str, str]] = {v: k for k, v in PROVIDERS.items()}
PROVIDER_KEYS: Final[List[str]] = list(PROVIDERS.values())

# ---------------------------------------------------------------------------
# Kryptomeny
# ---------------------------------------------------------------------------
SUPPORTED_COINS: Final[List[str]] = [
    "BTC", "ETH", "SOL", "BNB", "XRP",
    "ADA", "DOGE", "AVAX", "DOT", "LINK",
]

MOCK_BASE_PRICES: Final[Dict[str, float]] = {
    "BTC": 62_000.0, "ETH": 3_400.0, "SOL": 145.0, "BNB": 580.0, "XRP": 0.55,
    "ADA": 0.45, "DOGE": 0.15, "AVAX": 28.0, "DOT": 6.5, "LINK": 14.0,
}

TIME_HORIZONS: Final[Dict[str, Dict[str, object]]] = {
    "24h": {"points": 24, "unit": "hodina"},
    "1T": {"points": 7, "unit": "den"},
    "1M": {"points": 30, "unit": "den"},
    "1R": {"points": 12, "unit": "mesiac"},
}

SECTOR_CATEGORIES: Final[List[str]] = ["DeFi", "L1/L2", "AI", "Memes", "Other"]

# ---------------------------------------------------------------------------
# Externe API
# ---------------------------------------------------------------------------
FEAR_GREED_API_URL: Final[str] = "https://api.alternative.me/fng/"
# Viacero zdrojov namiesto jedneho RSS feedu - diverzifikuje spravy naprieč
# nezavislymi redakciami (nie len jeden pohlad). Instagram/Facebook nemaju
# realny verejny sposob, ako z nich cerpat krypto obsah bez business API
# schvalenia, a X/Twitter API je od zmeny vlastnika platene - ani jedno teda
# nie je v tomto zozname. Reddit (r/CryptoCurrency) je pridany samostatne
# nizsie (REDDIT_CRYPTO_URL), kedze pouziva iny format (JSON, nie RSS).
CRYPTO_NEWS_RSS_URLS: Final[List[str]] = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]
REDDIT_CRYPTO_URL: Final[str] = "https://www.reddit.com/r/CryptoCurrency/hot.json"

GEMINI_API_URL_TEMPLATE: Final[str] = (
    "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}"
)
OPENAI_API_URL: Final[str] = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL: Final[str] = "gpt-4o-mini"
ANTHROPIC_API_URL: Final[str] = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL: Final[str] = "claude-3-5-haiku-20241022"
ANTHROPIC_API_VERSION: Final[str] = "2023-06-01"
DEEPSEEK_API_URL: Final[str] = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL: Final[str] = "deepseek-chat"
GROK_API_URL: Final[str] = "https://api.x.ai/v1/chat/completions"
GROK_MODEL: Final[str] = "grok-2-latest"

# ---------------------------------------------------------------------------
# CORS - povolene originy pre frontend dev server / produkciu
# ---------------------------------------------------------------------------
CORS_ORIGINS: Final[List[str]] = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# ---------------------------------------------------------------------------
# CoinGecko (live ceny + vyhladavanie mincí)
# ---------------------------------------------------------------------------
COINGECKO_SIMPLE_PRICE_URL: Final[str] = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_SEARCH_URL: Final[str] = "https://api.coingecko.com/api/v3/search"
COINGECKO_COINS_LIST_URL: Final[str] = "https://api.coingecko.com/api/v3/coins/list"
PRICE_CACHE_TTL_SECONDS: Final[int] = 60

# Mapovanie zakladnych symbolov na CoinGecko id (pre vyhladavaciu ponuku aj mock data).
DEFAULT_COIN_IDS: Final[Dict[str, str]] = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink",
}

# ---------------------------------------------------------------------------
# Odkazy na ziskanie API klucov (Account page)
# ---------------------------------------------------------------------------
PROVIDER_KEY_LINKS: Final[Dict[str, str]] = {
    "gemini": "https://aistudio.google.com/app/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "grok": "https://console.x.ai/",
}

# Priblizna cena za 1000 vystupnych tokenov (USD) - iba orientacny odhad pre UI.
PROVIDER_TOKEN_PRICE_USD_PER_1K: Final[Dict[str, float]] = {
    "gemini": 0.0007,
    "openai": 0.0006,
    "anthropic": 0.001,
    "deepseek": 0.00028,
    "grok": 0.0005,
}

# ---------------------------------------------------------------------------
# Account lockout (brute-force ochrana pri prihlaseni)
# ---------------------------------------------------------------------------
MAX_FAILED_LOGIN_ATTEMPTS: Final[int] = 5
ACCOUNT_LOCKOUT_MINUTES: Final[int] = 15

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per proces - pre viac-procesove nasadenie by
# bolo treba zdielany store ako Redis, ale pre tuto appku staci)
# ---------------------------------------------------------------------------
RATE_LIMIT_LOGIN: Final[tuple] = (10, 60)          # 10 pokusov / 60s na IP
RATE_LIMIT_AI_ENDPOINT: Final[tuple] = (20, 60)    # 20 AI volani / 60s na pouzivatela
RATE_LIMIT_CHAT: Final[tuple] = (30, 60)
RATE_LIMIT_ACCOUNT_SENSITIVE: Final[tuple] = (5, 60)   # zmena hesla/emailu/odhlasenie vsade
RATE_LIMIT_API_KEY_TEST: Final[tuple] = (10, 60)        # tlacidlo "Testovat" pri API klucoch
RATE_LIMIT_VOTE: Final[tuple] = (10, 60)               # community sentiment hlasovanie
RATE_LIMIT_MARKET_PUBLIC: Final[tuple] = (30, 60)      # verejne (neautentifikovane) market endpointy
RATE_LIMIT_RESET_CODE: Final[tuple] = (8, 300)         # over/znovu-posli kod na reset hesla (brute-force ochrana)

# ---------------------------------------------------------------------------
# Password reset (funguje aj bez SMTP: v development rezime sa reset link
# vrati priamo v API odpovedi + vypise do konzoly; v produkcii treba
# nastavit SMTP_* premenne, inak sa link iba loguje na serveri).
# ---------------------------------------------------------------------------
PASSWORD_RESET_TOKEN_MINUTES: Final[int] = 15
# Render (a viacero inych bezplatnych PaaS platforiem) od konca roka 2025
# blokuje na bezplatnom pláne VSETKY odchadzajuce spojenia na SMTP porty
# (25/465/587) kvoli ochrane pred spamom - priame SMTP tym padom z takehoto
# hostingu proste nikdy neprejde, bez ohladu na spravnost udajov. BREVO_API_KEY
# umoznuje poslat email cez ich HTTPS API (port 443) namiesto SMTP - to
# blokovane nie je. Ak je nastaveny, ma prednost pred SMTP_* nizsie.
BREVO_API_KEY: Final[str] = os.environ.get("BREVO_API_KEY", "")
EMAIL_FROM: Final[str] = os.environ.get("EMAIL_FROM", "no-reply@ai-crypto-analytics.local")
SMTP_HOST: Final[str] = os.environ.get("SMTP_HOST", "")
SMTP_PORT: Final[int] = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER: Final[str] = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD: Final[str] = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM: Final[str] = os.environ.get("SMTP_FROM", EMAIL_FROM)
FRONTEND_URL: Final[str] = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# ---------------------------------------------------------------------------
# CSRF (double-submit cookie)
# ---------------------------------------------------------------------------
CSRF_COOKIE_NAME: Final[str] = "aca_csrf"
CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"
