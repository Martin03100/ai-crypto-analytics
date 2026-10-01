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
Sentry (`SENTRY_DSN`, `VITE_SENTRY_DSN`), CoinGecko/Blockchair API keys.

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
  claimed in the database, so several workers never run it twice). On Render's free plan the keep-warm workflow keeps
  the service awake; a sleeping service runs overdue schedules as soon as it wakes. Set `SCHEDULER_ENABLED=0` to turn it off.
- Free-tier market APIs (CoinGecko) limit history to about a year, so very old forecasts may no longer be scorable.

## Disclaimer

Forecasts are for information only and are not investment advice.
