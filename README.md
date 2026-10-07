# AI Crypto Analytics

[![CI](https://github.com/Martin03100/ai-crypto-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/Martin03100/ai-crypto-analytics/actions/workflows/ci.yml)

Web application for cryptocurrency analysis that combines forecasts from large language models with a transparent
statistical model and real market data. Bachelor's thesis project (Software Development, Unicorn University, Prague).

**Live demo:** https://aicryptopredictor.netlify.app · **Service status:** https://aicryptopredictor.netlify.app/status

## Features

- **AI forecasts** from Gemini, OpenAI, Anthropic Claude, DeepSeek, xAI Grok or any OpenAI-compatible API (user's own key),
  with a **side-by-side model comparison** chart.
- **Free statistical model** with an 80% uncertainty band; it also serves as an automatic fallback when an AI provider fails.
- **Walk-forward backtest** of the statistical model on real history (MAPE vs. naive forecast, band coverage, direction
  accuracy) and automatic accuracy evaluation of every saved forecast, with a leaderboard.
- **Scheduled forecasts:** the server creates and saves a forecast daily or weekly at the user's local time
  (time zone and daylight saving aware), so the accuracy history builds up on its own.
- **Watchlist** of followed coins with live price and 24h change on the dashboard; **CSV export** of the forecast history.
- **Installable app (PWA)** with offline mode: the app shell and the last loaded data (history, prices, watchlist)
  stay available without a connection for 24 hours after the last online sign-in; offline data is deleted on sign-out.
- **Portfolio advisor** with CSV import (generic or exchange balance export).
- **Market sentiment:** Fear & Greed index, news, on-chain whale activity, official FOMC/CPI calendar.
- **Public share links** for forecasts, **account activity log**, **new-device sign-in alerts**, optional 2FA.
- **Public track record** (`/track-record`) with share buttons and auto-generated preview images for social networks
  (Netlify Edge Function + Pillow cards), plus **robots.txt / sitemap / JSON-LD**.
- **Community:** "Beat the AI" price duels with a weekly and all-time tipster board (opt-in nicknames), in-app
  **notifications** when forecasts are checked or duels end, and an opt-in **weekly "AI vs reality" email**.
- **Market signals** from public, keyless sources, shown to users and fed into every AI analysis (forecast, portfolio,
  news summary, digest, chat and the morning briefing): funding, open interest, long/short ratio (Binance → Bybit → OKX
  fallback), liquidations (OKX), options put/call and implied volatility (Deribit), stablecoin supply (DefiLlama),
  Coinbase premium, BTC dominance and total market cap, Bitcoin fees and hashrate (mempool.space), VIX, Nasdaq,
  S&P 500, dollar, yields, oil, Fed rate and CPI (FRED), gold, the Fed/CPI calendar, SEC and CFTC news and Polymarket odds.
  Each analysis keeps the exact values it used, so users can check the reasoning.
- **Free tools:** **market scanner** (expected 24h move, RSI and a signal for the top 5 coins) and **smart alerts**
  (price level, big 24h move, RSI extremes).
- **20 coins** (incl. TON, SUI, PEPE…) and a **4-hour horizon** next to 24h / 1 week / 1 month / 1 year.
- **Premium** (Stripe, monthly or yearly, 7-day trial): **AI consensus** weighted by each model's track record,
  **smart model pick** (most accurate AI per coin and horizon, Bayesian-shrunk), **strategy simulator** on real past
  forecasts (fees, shorts, drawdown vs. buy & hold), the **full scanner** (20 coins), **portfolio P&L tracker** with risk
  score and daily history, **PDF report**, **Telegram** delivery, Fear & Greed alerts, up to 25 alerts, a **morning
  briefing**, **personal accuracy stats** and 20 scheduled forecasts. Checkout requires accepting the Terms and stays off
  until the seller details are filled in. **GDPR data export** for every user.
- **Premium mode switch:** the admin can hide everything paid (prices, Premium pages, seller details, paid features)
  with one switch; it is off by default, so the app looks fully free until payments are ready.
- **Invites:** a friend who signs up with your link gets a 14-day trial; when they pay, the inviter gets 30 days of
  Premium. With Premium off, invites earn bronze / silver / gold **ambassador badges** on the public board.
- **Admin panel** (`/admin`, users listed in `ADMIN_USERNAMES`, 2FA required): stats, user search, granting or removing
  Premium, blocking accounts, waitlist CSV export, the Premium mode switch, feature switches, limits and a site-wide
  announcement banner. **Payments tab:** paste one Stripe secret key (stored encrypted) and set prices; the app creates
  the Stripe product, prices, webhook and customer portal and shows a checklist of what is still missing before selling.
- **Beat the AI:** a weekly challenge on one rotating coin - tips close on Thursday, the closest guess wins a badge
  shown on the tipster board and in the profile.
- **Honest accuracy:** confidence calibration (claimed vs. real hit rate), accuracy by market situation (rising,
  falling, sideways) and a comparison of every forecast with a naive "price stays the same" guess.
- **Sharing:** forecasts as Story (9:16) and post (1:1) images, invite link as a QR code.
- **SEO coin pages:** 20 coins in English, Slovak and Czech (`/prediction/bitcoin`, `/sk/predikcia/bitcoin`,
  `/cs/predikce/bitcoin`); a Netlify edge function adds the title, canonical, hreflang, JSON-LD and a text snippet.
- **Status page** with 30 days of availability history, a "server is waking up" banner on slow responses and a
  one-click **database backup** (gzipped JSON) in the admin panel.
- Transactional emails in **English, Slovak and Czech**, following the user's app language.
- **Demo mode** for presentations: one click fills the whole app with clearly labelled test data ("Gemini test", "Claude test", ...)
  on synthetic prices - forecasts, evaluated accuracy, leaderboard, tips and portfolio analyses, visible only to the user who loaded it.

## Architecture

```
Browser (React + Vite, Netlify)
   │  /api (same-origin proxy), HttpOnly cookie + CSRF token
   ▼
REST API (FastAPI, Render) ── rate limiting, validation, security headers, optional Sentry
   │
   ├── Services: AI engine, statistical model, backtest, accuracy evaluation, audit log
   ├── Database: PostgreSQL (production) / SQLite (development) via SQLAlchemy
   └── External: CoinGecko, Alternative.me, Blockchair, news RSS, AI provider APIs (cached, with fallbacks)
```

## Quality and testing

| Layer | Tool | What it covers |
| --- | --- | --- |
| Backend | pytest | API, security (auth, CSRF, rate limits, lockout, 2FA), models, backtest on real BTC data, fallbacks |
| Frontend | Vitest | API client, parsers (CSV), formatting, translations, pure UI logic |
| End-to-end | Playwright | Sign-up / sign-in / activity log, CSV import, demo data (history, leaderboard, portfolio, dashboard), model tabs, public pages, redirects |
| Lint | ruff, ESLint | Backend (pyflakes, bugbear) and frontend (React hook rules, unused code) |
| CI | GitHub Actions | All of the above on every push and pull request |

## Running locally

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows; on Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                              # fill in secrets, see comments in the file
uvicorn app.main:app --reload --port 8000
python -m pytest -q                               # tests
ruff check .                                      # lint
```

Frontend (Node 22):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to the backend
npm test             # unit tests
npm run lint         # ESLint
npx playwright install chromium && npm run test:e2e   # end-to-end tests (start both servers automatically)
```

## Configuration

Secrets are read from environment variables only (see `backend/.env.example` and `frontend/.env.example`).
Optional integrations stay off when their variable is empty: email (Brevo/SMTP), Cloudflare Turnstile,
Sentry (`SENTRY_DSN`, `VITE_SENTRY_DSN`), CoinGecko/Blockchair API keys, Stripe (`STRIPE_*`) and Umami analytics
(`VITE_UMAMI_WEBSITE_ID`).

## Database migrations

The schema is managed by [Alembic](https://alembic.sqlalchemy.org/) (`backend/migrations`). The backend applies
pending migrations on startup (`alembic upgrade head`), so a deploy needs no extra step. A database created before
migrations existed is detected, completed and stamped as the baseline automatically.

After changing a model in `app/models.py`:

```bash
cd backend
alembic revision --autogenerate -m "short description"   # review the generated file in migrations/versions
alembic upgrade head
```

`tests/test_migrations.py` fails when a model changes without a matching migration.

## Known limitations

- **Rate limits are kept in process memory.** They are exact for a single backend instance (the current Render
  setup), but reset on restart and are counted separately per worker or instance. Scaling out would need a shared
  store such as Redis.
- **`TRUSTED_PROXY_HOPS` must match the deployment.** Behind the Netlify `/api` proxy and Render it is `2`;
  otherwise rate limits and the activity log see a proxy's IP instead of the user's (see `backend/.env.example`).
- **Scheduled forecasts run inside the backend process** (a background thread polling every minute; each run is
  claimed in the database, so several workers never run it twice). Set `SCHEDULER_ENABLED=0` to turn it off.
- **Render free plan sleeps after ~15 minutes without traffic.** The backend pings its own public URL
  (`RENDER_EXTERNAL_URL`, set by Render) every 10 minutes to stay awake (`KEEP_AWAKE=0` turns it off); GitHub's
  scheduled keep-warm workflow is only a backup, as GitHub runs it every few hours at best. A running service uses
  about 744 of the 750 free instance hours per month. A sleeping service runs overdue schedules as soon as it wakes.
- Free-tier market APIs (CoinGecko) limit history to about a year, so very old forecasts may no longer be scorable.

## Disclaimer

Forecasts are for information only and are not investment advice.
