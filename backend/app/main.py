"""
app/main.py
============
FastAPI vstupny bod. Konfiguruje logging, CORS, CSRF, bezpecnostne hlavicky,
inicializuje DB (vratane auto-migracie chybajucich stlpcov) a registruje
routery. Ziadna business logika sa tu nenachadza.

Spustenie (dev):
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import APP_ENV, APP_TITLE, CORS_ORIGINS
from app.csrf import CSRFMiddleware
from app.database import SessionLocal, init_db
from app.logging_config import configure_logging
from app.routers import account, auth, chat, forecast, market, portfolio
from app.security_headers import SecurityHeadersMiddleware

configure_logging()
logger = logging.getLogger("aca.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Modernejsi nahradok za @app.on_event("startup") (ten je vo FastAPI
    # deprecated a v buducej verzii moze byt odstraneny). Kod PRED yield
    # bezi pri starte servera, kod PO yield (ziadny tu zatial netreba) by
    # bezal pri vypnuti.
    init_db()
    logger.info("AI Crypto Analytics backend spusteny.")
    yield


# V produkcii vypneme interaktivnu API dokumentaciu (/docs, /redoc) a surovu
# OpenAPI schemu (/openapi.json) - v opacnom pripade by boli verejne
# dostupne komukolvek na internete a odhalovali by kompletnu strukturu API
# (nazvy vsetkych poli, endpointov...), co je zbytocny "recon" material pre
# utocnika. V developmente ostavaju zapnute pre pohodlne testovanie.
_docs_enabled = APP_ENV != "production"
app = FastAPI(
    title=APP_TITLE,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Nikdy nevratit surovy stacktrace klientovi (unika interne detaily);
    # zaloguj ho strukturovane na serveri, kde sa da dohladat.
    logger.error("Neosetrena vynimka na %s %s: %s", request.method, request.url.path, exc, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Nastala neočakávaná chyba na serveri."})


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(forecast.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict:
    """Health check pre monitoring/uptime nastroje a deployment platformy
    (Render a pod. ho pouzivaju na zistenie, ci je instancia zdrava).
    Overuje aj skutocne pripojenie k DB - ak by appka bezala, ale DB bola
    nedostupna, cisty 'appka bezi' health check by to neodhalil."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - health check nikdy nesmie sam spadnut
        db_ok = False
    status_code = 200 if db_ok else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if db_ok else "degraded", "database": db_ok})
