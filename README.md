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
```

Frontend (Node 22):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to the backend
npm test             # unit tests
npx playwright install chromium && npm run test:e2e   # end-to-end tests (start both servers automatically)
```

## Configuration

Secrets are read from environment variables only (see `backend/.env.example` and `frontend/.env.example`).
Optional integrations stay off when their variable is empty: email (Brevo/SMTP), Cloudflare Turnstile,
Sentry (`SENTRY_DSN`, `VITE_SENTRY_DSN`), CoinGecko/Blockchair API keys.

## Disclaimer

Forecasts are for information only and are not investment advice.
