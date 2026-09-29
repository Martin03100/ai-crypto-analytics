"""FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import APP_ENV, APP_TITLE, CORS_ORIGINS, validate_production_config
from app.csrf import CSRFMiddleware
from app.database import SessionLocal, init_db
from app.logging_config import configure_logging
from app.routers import account, auth, chat, forecast, market, portfolio
from app.request_guard import RequestGuardMiddleware
from app.security_headers import SecurityHeadersMiddleware

configure_logging()
logger = logging.getLogger("aca.main")

validate_production_config()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("AI Crypto Analytics backend spusteny.")
    yield


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
app.add_middleware(RequestGuardMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        db_ok = False
    status_code = 200 if db_ok else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if db_ok else "degraded", "database": db_ok})
