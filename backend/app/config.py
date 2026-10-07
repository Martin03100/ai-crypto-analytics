"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Final, List, Optional

APP_TITLE: Final[str] = "AI Crypto Analytics"
REQUEST_TIMEOUT_SECONDS: Final[int] = 12
# Per-attempt timeout for AI provider calls. The web app runs AI requests as background jobs (app/services/jobs.py)
# and polls for the result, so the ~26 s limit of the Netlify /api proxy does not apply to the model call.
AI_REQUEST_TIMEOUT_SECONDS: Final[int] = int(os.environ.get("AI_REQUEST_TIMEOUT_SECONDS", "45"))

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
DB_PATH: Final[Path] = DATA_DIR / "app.db"
DATABASE_URL: Final[str] = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

JWT_SECRET_KEY: Final[str] = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me-in-production")
JWT_ALGORITHM: Final[str] = "HS256"
PASSWORD_HASH_ROUNDS: Final[int] = int(os.environ.get("PASSWORD_HASH_ROUNDS", "310000"))
JWT_EXPIRE_MINUTES: Final[int] = 60 * 24 * 7

AUTH_COOKIE_NAME: Final[str] = "aca_session"
AUTH_COOKIE_MAX_AGE_SECONDS: Final[int] = JWT_EXPIRE_MINUTES * 60
APP_ENV: Final[str] = os.environ.get("APP_ENV", "development")
AUTH_COOKIE_SECURE: Final[bool] = APP_ENV == "production"
AUTH_COOKIE_SAMESITE: Final[str] = "lax"

API_KEY_ENCRYPTION_SECRET: Final[str] = os.environ.get(
    "API_KEY_ENCRYPTION_SECRET", "dev-fernet-key-change-me-in-production-32b"
)

PROVIDERS: Final[Dict[str, str]] = {
    "Gemini": "gemini",
    "OpenAI (ChatGPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "DeepSeek": "deepseek",
    "Grok (xAI)": "grok",
    "Custom (OpenAI-compatible)": "custom",
}
PROVIDER_LABELS: Final[Dict[str, str]] = {v: k for k, v in PROVIDERS.items()}
PROVIDER_KEYS: Final[List[str]] = list(PROVIDERS.values())

QUANT_PROVIDER: Final[str] = "quant"
QUANT_LABEL: Final[str] = "Quant (free model)"


def provider_label(provider: str) -> Optional[str]:
    """Display label stored with a forecast, or None for an unknown provider."""
    if provider == QUANT_PROVIDER:
        return QUANT_LABEL
    return PROVIDER_LABELS.get(provider)

SUPPORTED_COINS: Final[List[str]] = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
    "TON", "TRX", "LTC", "BCH", "SHIB", "SUI", "PEPE", "NEAR", "APT", "UNI",
]

MOCK_BASE_PRICES: Final[Dict[str, float]] = {
    "BTC": 83_000.0, "ETH": 2_850.0, "SOL": 115.0, "BNB": 800.0, "XRP": 1.60,
    "ADA": 0.36, "DOGE": 0.12, "AVAX": 12.0, "DOT": 1.15, "LINK": 12.0,
    "TON": 2.5, "TRX": 0.30, "LTC": 90.0, "BCH": 450.0, "SHIB": 0.000012, "SUI": 2.8, "PEPE": 0.00001,
    "NEAR": 2.4, "APT": 4.5, "UNI": 7.5,
}

TIME_HORIZONS: Final[Dict[str, Dict[str, object]]] = {
    "4h": {"points": 4, "unit": "hodina"},
    "24h": {"points": 24, "unit": "hodina"},
    "1T": {"points": 7, "unit": "den"},
    "1M": {"points": 30, "unit": "den"},
    "1R": {"points": 12, "unit": "mesiac"},
}

SECTOR_CATEGORIES: Final[List[str]] = ["DeFi", "L1/L2", "AI", "Memes", "Other"]

FEAR_GREED_API_URL: Final[str] = "https://api.alternative.me/fng/"
CRYPTO_NEWS_RSS_URLS: Final[List[str]] = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://cryptoslate.com/feed/",
]
REDDIT_CRYPTO_URL: Final[str] = "https://www.reddit.com/r/CryptoCurrency/hot.json"

GEMINI_MODEL: Final[str] = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# Tried in order when the main model is overloaded, failing or out of quota (comma separated; empty = none).
GEMINI_FALLBACK_MODELS: Final[List[str]] = [
    m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-flash-lite-latest").split(",") if m.strip()
]
OPENAI_API_URL: Final[str] = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL: Final[str] = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_URL: Final[str] = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL: Final[str] = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_API_VERSION: Final[str] = "2023-06-01"
DEEPSEEK_API_URL: Final[str] = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL: Final[str] = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
GROK_API_URL: Final[str] = "https://api.x.ai/v1/chat/completions"
GROK_MODEL: Final[str] = os.environ.get("GROK_MODEL", "grok-4.3")

CORS_ORIGINS: Final[List[str]] = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

COINGECKO_SIMPLE_PRICE_URL: Final[str] = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_SEARCH_URL: Final[str] = "https://api.coingecko.com/api/v3/search"
COINGECKO_COINS_LIST_URL: Final[str] = "https://api.coingecko.com/api/v3/coins/list"
PRICE_CACHE_TTL_SECONDS: Final[int] = 60
COINGECKO_API_KEY: Final[str] = os.environ.get("COINGECKO_API_KEY", "")
FRED_API_KEY: Final[str] = os.environ.get("FRED_API_KEY", "")
GITHUB_TOKEN: Final[str] = os.environ.get("GITHUB_TOKEN", "")
BLOCKCHAIR_API_KEY: Final[str] = os.environ.get("BLOCKCHAIR_API_KEY", "")
TURNSTILE_SECRET_KEY: Final[str] = os.environ.get("TURNSTILE_SECRET_KEY", "")
EMAIL_VERIFICATION_CODE_MINUTES: Final[int] = 30

DEFAULT_COIN_IDS: Final[Dict[str, str]] = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "TON": "the-open-network", "TRX": "tron", "LTC": "litecoin",
    "BCH": "bitcoin-cash", "SHIB": "shiba-inu", "SUI": "sui", "PEPE": "pepe", "NEAR": "near", "APT": "aptos",
    "UNI": "uniswap",
}

HORIZON_HOURS: Final[Dict[str, int]] = {"4h": 4, "24h": 24, "1T": 7 * 24, "1M": 30 * 24, "1R": 365 * 24}

PROVIDER_KEY_LINKS: Final[Dict[str, str]] = {
    "gemini": "https://aistudio.google.com/app/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "grok": "https://console.x.ai/",
    "custom": "https://openrouter.ai/keys",
}

PROVIDER_TOKEN_PRICE_USD_PER_1K: Final[Dict[str, float]] = {
    "gemini": 0.0007,
    "openai": 0.0006,
    "anthropic": 0.001,
    "deepseek": 0.00028,
    "grok": 0.0005,
    "custom": 0.0008,
}

MAX_FAILED_LOGIN_ATTEMPTS: Final[int] = 5
# Background thread that runs users' scheduled forecasts (off in tests).
SCHEDULER_ENABLED: Final[bool] = os.environ.get("SCHEDULER_ENABLED", "1") != "0"
# Upper bound on saved forecasts / portfolio analyses per user (keeps one account from filling the database).
MAX_SAVED_ITEMS_PER_USER: Final[int] = int(os.environ.get("MAX_SAVED_ITEMS_PER_USER", "1000"))
ACCOUNT_LOCKOUT_MINUTES: Final[int] = 15

RATE_LIMIT_LOGIN: Final[tuple] = (int(os.environ.get("RATE_LIMIT_LOGIN_PER_MINUTE", "10")), 60)
RATE_LIMIT_AI_ENDPOINT: Final[tuple] = (20, 60)
RATE_LIMIT_CHAT: Final[tuple] = (30, 60)
RATE_LIMIT_ACCOUNT_SENSITIVE: Final[tuple] = (5, 60)
RATE_LIMIT_API_KEY_TEST: Final[tuple] = (10, 60)
RATE_LIMIT_VOTE: Final[tuple] = (10, 60)
RATE_LIMIT_MARKET_PUBLIC: Final[tuple] = (30, 60)
RATE_LIMIT_WAITLIST: Final[tuple] = (5, 300)
RATE_LIMIT_RESET_CODE: Final[tuple] = (8, 300)
RATE_LIMIT_MARKET_GLOBAL: Final[tuple] = (600, 60)
TRUSTED_PROXY_HOPS: Final[int] = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))

PASSWORD_RESET_TOKEN_MINUTES: Final[int] = 15
BREVO_API_KEY: Final[str] = os.environ.get("BREVO_API_KEY", "")
EMAIL_FROM: Final[str] = os.environ.get("EMAIL_FROM", "no-reply@ai-crypto-analytics.local")
SMTP_HOST: Final[str] = os.environ.get("SMTP_HOST", "")
SMTP_PORT: Final[int] = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER: Final[str] = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD: Final[str] = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM: Final[str] = os.environ.get("SMTP_FROM", EMAIL_FROM)
FRONTEND_URL: Final[str] = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Premium (Stripe). Billing stays off until all three are set; the app then shows the waitlist instead.
TELEGRAM_BOT_TOKEN: Final[str] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME: Final[str] = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@")
STRIPE_SECRET_KEY: Final[str] = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID: Final[str] = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_PRICE_ID_YEARLY: Final[str] = os.environ.get("STRIPE_PRICE_ID_YEARLY", "")
STRIPE_WEBHOOK_SECRET: Final[str] = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PREMIUM_PRICE_LABEL: Final[str] = os.environ.get("PREMIUM_PRICE_LABEL", "€4.99 / month")
APP_PUBLIC_URL: Final[str] = os.environ.get("APP_PUBLIC_URL", "https://aicryptopredictor.netlify.app").rstrip("/")
REFERRAL_REWARD_DAYS: Final[int] = 30
# Usernames with access to the admin panel (comma separated, case-insensitive). Admins must have 2FA on.
ADMIN_USERNAMES: Final[frozenset] = frozenset(
    u.strip().lower() for u in os.environ.get("ADMIN_USERNAMES", "").split(",") if u.strip())
MAX_REWARDED_REFERRALS: Final[int] = 12

CSRF_COOKIE_NAME: Final[str] = "aca_csrf"
CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"


_INSECURE_SECRETS = {
    "replace-with-a-random-secret",
    "replace-with-another-random-secret",
    "dev-secret-change-me-in-production",
    "dev-fernet-key-change-me-in-production-32b",
    "zmen-ma-na-nahodny-64-znakovy-retazec",
    "zmen-ma-na-iny-nahodny-retazec-pre-fernet",
}


def validate_production_config() -> None:
    if APP_ENV != "production":
        return
    import logging
    problems = []
    for name, value in (("JWT_SECRET_KEY", JWT_SECRET_KEY), ("API_KEY_ENCRYPTION_SECRET", API_KEY_ENCRYPTION_SECRET)):
        if value in _INSECURE_SECRETS or not value.strip():
            problems.append(f"{name} ma predvolenu (verejne znamu) hodnotu - nastav nahodny retazec (aspon 32 znakov).")
        elif len(value) < 32:
            logging.getLogger("aca.config").warning(
                "%s je kratsi nez 32 znakov - odporucame dlhsi nahodny retazec (pri API_KEY_ENCRYPTION_SECRET "
                "vsak zmena znehodnoti ulozene API kluce pouzivatelov).", name)
    if PASSWORD_HASH_ROUNDS < 100_000:
        problems.append("PASSWORD_HASH_ROUNDS musi byt v produkcii aspon 100000.")
    if problems:
        raise RuntimeError("Nebezpecna konfiguracia produkcie: " + " ".join(problems))
