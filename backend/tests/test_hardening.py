"""Security hardening tests."""

import json
import time
from unittest.mock import patch

import pytest

from tests.conftest import csrf_headers


def _register(client, username, email, password="TestPass123"):
    return client.post("/api/auth/register", json={"username": username, "password": password, "email": email})


@pytest.mark.parametrize("bad", ["   ", "ab", "meno s medzerou", "a" * 33, "<script>", "člověk"])
def test_register_rejects_invalid_usernames(client, bad):
    res = _register(client, bad, "x@example.com")
    assert res.status_code in (400, 422), f"{bad!r} must be rejected"


def test_username_is_unique_case_insensitively(client):
    assert _register(client, "Martin", "m1@example.com").status_code == 201
    client.cookies.clear()
    assert _register(client, "martin", "m2@example.com").status_code == 400


def test_login_finds_user_regardless_of_case(client):
    assert _register(client, "Martin", "m1@example.com").status_code == 201
    client.cookies.clear()
    res = client.post("/api/auth/login", json={"username": "MARTIN", "password": "TestPass123"})
    assert res.status_code == 200


def test_old_weak_password_hash_is_upgraded_on_login(client):
    from passlib.context import CryptContext
    from app.database import SessionLocal
    from app.models import User
    from app.security import needs_rehash
    assert _register(client, "olduser", "old@example.com").status_code == 201
    weak = CryptContext(schemes=["pbkdf2_sha256"], pbkdf2_sha256__default_rounds=500).hash("TestPass123")
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "olduser").update({"password_hash": weak})
        db.commit()
        assert needs_rehash(weak)
    finally:
        db.close()
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"username": "olduser", "password": "TestPass123"}).status_code == 200
    db = SessionLocal()
    try:
        assert not needs_rehash(db.query(User).filter(User.username == "olduser").one().password_hash)
    finally:
        db.close()


def test_provider_error_never_contains_api_key(registered):
    client, _u, _p = registered
    secret = "sk-SUPERSECRETKEY123456"
    client.put("/api/account/api-keys", json={"provider": "openai", "api_key": secret}, headers=csrf_headers(client))
    with patch("app.services.ai_engine._call_ai_provider_raw", return_value=(False, "", f"API chyba: bad key {secret}")):
        res = client.post("/api/chat", json={"provider": "openai", "messages": [{"role": "user", "content": "hi"}]},
                          headers=csrf_headers(client))
    assert secret not in res.text
    assert "***" in res.text


def test_custom_provider_key_is_redacted_from_errors():
    from app.services.ai_engine import call_ai_provider
    blob = json.dumps({"base_url": "https://x.example", "model": "m", "key": "TOPSECRETVALUE99"})
    with patch("app.services.ai_engine._call_ai_provider_raw", return_value=(False, "", "chyba TOPSECRETVALUE99")):
        ok, _t, err = call_ai_provider("custom", "p", blob)
    assert not ok and "TOPSECRETVALUE99" not in err


def test_chat_rejects_system_role_and_oversized_message(registered):
    client, _u, _p = registered
    h = csrf_headers(client)
    assert client.post("/api/chat", json={"provider": "openai", "messages": [{"role": "system", "content": "x"}]}, headers=h).status_code == 422
    assert client.post("/api/chat", json={"provider": "openai", "messages": [{"role": "user", "content": "x" * 9000}]}, headers=h).status_code == 422


def test_holding_symbol_and_coin_id_are_limited(registered):
    client, _u, _p = registered
    h = csrf_headers(client)
    body = {"provider": "openai", "holdings": [{"minca": "A" * 100000, "mnozstvo": 1}]}
    assert client.post("/api/portfolio/estimate-cost", json=body, headers=h).status_code == 422
    body = {"provider": "openai", "holdings": [{"minca": "BTC", "mnozstvo": 1, "coin_id": "../search"}]}
    assert client.post("/api/portfolio/estimate-cost", json=body, headers=h).status_code == 422


@pytest.mark.parametrize("url", [
    "/api/market/prices?ids=../search",
    "/api/market/prices?ids=bitcoin&vs_currency=xxx",
    "/api/market/chart?coin_id=../x",
    "/api/market/chart?coin_id=bitcoin&days=99999",
    "/api/market/chart?coin_id=bitcoin&vs_currency=zzz",
])
def test_market_endpoints_reject_bad_parameters(client, url):
    assert client.get(url).status_code == 400


def test_saved_json_size_is_limited(registered):
    client, _u, _p = registered
    payload = {"provider": "gemini", "coin": "BTC", "horizon": "1T", "is_mock": True,
               "forecast_data": {"ceny": [1], "casove_body": ["a"], "odovodnenie": "x" * 100_000}}
    assert client.post("/api/forecast/save", json=payload, headers=csrf_headers(client)).status_code == 422


def test_rss_links_only_allow_http(client):
    from app.services.market_data import safe_http_url
    assert safe_http_url("javascript:alert(1)") == ""
    assert safe_http_url(" data:text/html,x") == ""
    assert safe_http_url("https://example.com/a") == "https://example.com/a"


def test_x_forwarded_for_uses_trusted_hop_from_the_right(monkeypatch):
    from starlette.requests import Request
    from app import rate_limit

    def make(xff):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())], "client": ("9.9.9.9", 1)})

    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 1)
    assert rate_limit.get_client_ip(make("1.1.1.1, 5.5.5.5")) == "5.5.5.5"
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 2)
    assert rate_limit.get_client_ip(make("1.1.1.1, 5.5.5.5, 6.6.6.6")) == "5.5.5.5"
    monkeypatch.setattr(rate_limit, "TRUSTED_PROXY_HOPS", 0)
    assert rate_limit.get_client_ip(make("1.1.1.1, 5.5.5.5")) == "1.1.1.1"


def test_rate_limiter_forgets_stale_keys(monkeypatch):
    from app import rate_limit
    rate_limit._hits.clear()
    for i in range(20):
        rate_limit._check(f"k{i}", 5, 60)
    assert len(rate_limit._hits) == 20
    real = time.monotonic()
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: real + rate_limit._STALE_AFTER_SECONDS + 10)
    rate_limit._sweep(time.monotonic())
    assert len(rate_limit._hits) == 0


def test_global_market_limit_holds_even_with_spoofed_ips(client, monkeypatch):
    from app.routers import market
    monkeypatch.setattr(market, "get_upcoming_market_events", lambda lang: [])
    codes = []
    for i in range(620):
        codes.append(client.get("/api/market/events", headers={"X-Forwarded-For": f"10.1.{i // 250}.{i % 250}"}).status_code)
    assert 429 in codes


def test_ttl_cache_is_bounded_and_prefers_dropping_expired():
    from app.utils.ttl_cache import TTLCache
    cache = TTLCache(ttl_seconds=60, max_entries=10)
    for i in range(50):
        cache.set(f"k{i}", i)
    assert len(cache._store) <= 10
    assert cache.get("k49") == 49
    assert cache.get("k0") is None


def _forecast(**over):
    base = {"ceny": [1.0, 2.0, 3.0], "casove_body": ["a", "b", "c"], "odovodnenie": "t", "confidence_score": 50, "risk_level": "Low"}
    base.update(over)
    return json.dumps(base)


def test_forecast_validator_rejects_non_numeric_negative_and_nan_prices():
    from app.services.validators import validate_forecast_payload as v
    assert not v(_forecast(ceny=["a", "b", "c"]))[0]
    assert not v(_forecast(ceny=[1, -2, 3]))[0]
    assert not v(_forecast(ceny=[1, None, 3]))[0]
    assert not v(_forecast(ceny=[True, 2, 3]))[0]
    assert v(_forecast())[0]


def test_forecast_validator_enforces_expected_number_of_points():
    from app.services.validators import validate_forecast_payload as v
    ok, data, err = v(_forecast(), expected_points=3)
    assert ok and len(data["ceny"]) == 3
    ok, data, err = v(_forecast(ceny=[1, 2, 3, 4], casove_body=list("abcd")), expected_points=3)
    assert ok and data["ceny"] == [1.0, 2.0, 3.0]
    assert not v(_forecast(), expected_points=24)[0]


def test_portfolio_and_news_validators_normalize_values():
    from app.services.validators import validate_news_payload, validate_portfolio_payload
    good = {"odporucania": [{"minca": "BTC", "akcia": "buy", "dovod": "x"}], "odborna_analyza": "x",
            "sektorova_alokacia": {"L1/L2": 50}, "rebalancing_checklist": ["a"]}
    ok, data, _ = validate_portfolio_payload(json.dumps(good))
    assert ok and data["odporucania"][0]["akcia"] == "BUY"
    bad = json.loads(json.dumps(good)); bad["odporucania"][0]["akcia"] = "YOLO"
    assert not validate_portfolio_payload(json.dumps(bad))[0]
    bad = json.loads(json.dumps(good)); bad["sektorova_alokacia"] = {"AI": "lots"}
    assert not validate_portfolio_payload(json.dumps(bad))[0]
    ok, data, _ = validate_news_payload(json.dumps({"spravy": [{"titulok": "t", "sentiment": "BULLISH"}, {"titulok": "u", "sentiment": "???"}], "trendy": ["x"]}))
    assert ok and [n["sentiment"] for n in data["spravy"]] == ["Bullish", "Neutral"]


def test_production_refuses_default_secrets(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "dev-secret-change-me-in-production")
    with pytest.raises(RuntimeError):
        config.validate_production_config()
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setattr(config, "API_KEY_ENCRYPTION_SECRET", "y" * 40)
    monkeypatch.setattr(config, "PASSWORD_HASH_ROUNDS", 310_000)
    config.validate_production_config()
    monkeypatch.setattr(config, "PASSWORD_HASH_ROUNDS", 1000)
    with pytest.raises(RuntimeError):
        config.validate_production_config()


def test_development_allows_default_secrets(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "APP_ENV", "development")
    config.validate_production_config()


def test_custom_base_url_rejects_private_and_ipv6_scope_ids(monkeypatch):
    from app.services import ai_engine
    fake = lambda host, port, proto=0: [(2, 1, 6, "", ("127.0.0.1", 443))]
    monkeypatch.setattr(ai_engine.socket, "getaddrinfo", fake)
    assert ai_engine.validate_custom_base_url("https://evil.example/v1")
    monkeypatch.setattr(ai_engine.socket, "getaddrinfo", lambda *a, **k: [(10, 1, 6, "", ("fe80::1%eth0", 443, 0, 2))])
    assert ai_engine.validate_custom_base_url("https://evil.example/v1")
    monkeypatch.setattr(ai_engine.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    assert ai_engine.validate_custom_base_url("https://ok.example/v1") is None
    assert ai_engine.validate_custom_base_url("http://ok.example/v1")


def test_auto_migrate_adds_missing_columns_independently(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from app import database
    engine = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64), password_hash VARCHAR(255))"))
        conn.execute(sa.text("INSERT INTO users (username, password_hash) VALUES ('a', 'h')"))
    monkeypatch.setattr(database, "engine", engine)
    database.auto_migrate()
    cols = {c["name"] for c in sa.inspect(engine).get_columns("users")}
    assert {"token_version", "failed_login_attempts", "email", "totp_enabled"} <= cols


def test_totp_required_response_carries_machine_readable_code(registered):
    from app.database import SessionLocal
    from app.models import User
    from app.security import encrypt_secret, generate_totp_secret
    client, username, password = registered
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one()
        user.totp_secret = encrypt_secret(generate_totp_secret(), user.id)
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()
    client.cookies.clear()
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 401 and res.headers.get("X-Error-Code") == "totp_required"


def test_custom_provider_blocks_dns_rebinding_and_never_sends_the_key(monkeypatch):
    import socket
    from app.services import ai_engine
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(3)
    port = server.getsockname()[1]
    monkeypatch.setattr(ai_engine, "validate_custom_base_url", lambda url: None)
    secret = json.dumps({"base_url": f"https://127.0.0.1:{port}", "model": "m", "key": "SECRETKEY123"})
    ok, _text, err = ai_engine._call_custom_provider("hello", secret)
    assert ok is False and "internú sieť" in err
    conn, _ = server.accept()
    conn.settimeout(1)
    try:
        received = conn.recv(4096)
    except socket.timeout:
        received = b""
    conn.close(); server.close()
    assert received == b"", "no data may be sent over a blocked connection"


def test_public_ip_helper():
    from app.services.ai_engine import _is_public_ip
    assert _is_public_ip("93.184.216.34")
    for bad in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "fe80::1%eth0", "not-an-ip", ""):
        assert not _is_public_ip(bad), bad


def _email_verification_on(monkeypatch):
    from app.routers import account as account_router, auth as auth_router
    from app.services import verification
    monkeypatch.setattr(auth_router, "is_email_configured", lambda: True)
    monkeypatch.setattr(account_router, "is_email_configured", lambda: True)
    monkeypatch.setattr(verification, "send_email", lambda *a, **k: True)


def test_unverified_account_cannot_squat_someones_email(client, monkeypatch):
    _email_verification_on(monkeypatch)
    assert _register(client, "utocnik", "obet@example.com").status_code == 201
    client.cookies.clear()
    assert _register(client, "obet", "obet@example.com").status_code == 201
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"username": "utocnik", "password": "TestPass123"}).status_code == 401


def test_verified_account_keeps_its_email(client, monkeypatch):
    from app.database import SessionLocal
    from app.models import User
    _email_verification_on(monkeypatch)
    assert _register(client, "povodny", "moj@example.com").status_code == 201
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "povodny").update({"email_verified": True}); db.commit()
    finally:
        db.close()
    client.cookies.clear()
    assert _register(client, "druhy", "moj@example.com").status_code == 400


def test_email_change_also_releases_unverified_holder(client, monkeypatch):
    _email_verification_on(monkeypatch)
    assert _register(client, "squatter", "cielovy@example.com").status_code == 201
    client.cookies.clear()
    assert _register(client, "majitel", "povodny@example.com").status_code == 201
    res = client.put("/api/account/email", json={"email": "cielovy@example.com"}, headers=csrf_headers(client))
    assert res.status_code == 200


def test_concurrent_duplicate_tip_returns_400_not_500(registered, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from tests.conftest import signed_forecast_payload
    client, _u, _p = registered
    entry_id = client.post("/api/forecast/save", json=signed_forecast_payload(client, horizon="24h"), headers=csrf_headers(client)).json()["id"]
    real_commit = Session.commit
    def failing_commit(self):
        if any(type(o).__name__ == "PriceTip" for o in self.new):
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        return real_commit(self)
    monkeypatch.setattr(Session, "commit", failing_commit)
    res = client.post(f"/api/forecast/history/{entry_id}/tip", json={"price": 100}, headers=csrf_headers(client))
    assert res.status_code == 400


def test_auto_migrate_on_postgres_adds_all_columns(monkeypatch):
    import os
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("potrebuje Postgres (TEST_DATABASE_URL=postgresql+psycopg2://...)")
    import sqlalchemy as sa
    from app import database
    eng = sa.create_engine(url)
    with eng.begin() as c:
        for t in ("password_reset_tokens", "users"):
            c.execute(sa.text(f"DROP TABLE IF EXISTS {t} CASCADE"))
        c.execute(sa.text("CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at TIMESTAMP)"))
        c.execute(sa.text("INSERT INTO users (username, password_hash) VALUES ('stary', 'h')"))
        c.execute(sa.text("CREATE TABLE password_reset_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, token_hash VARCHAR(64) NOT NULL, expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP)"))
        c.execute(sa.text("INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (1, 'x', now())"))
    monkeypatch.setattr(database, "engine", eng)
    database.auto_migrate()
    users = {c["name"] for c in sa.inspect(eng).get_columns("users")}
    assert {"token_version", "failed_login_attempts", "email", "locked_until", "email_verified", "totp_secret", "totp_enabled"} <= users
    assert "used" in {c["name"] for c in sa.inspect(eng).get_columns("password_reset_tokens")}
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT username, token_version FROM users")).all() == [("stary", 0)]
    with eng.begin() as c:
        for t in ("password_reset_tokens", "users"):
            c.execute(sa.text(f"DROP TABLE IF EXISTS {t} CASCADE"))


def _manual_hs256(payload: dict, secret: str, header=None) -> str:
    import base64, hashlib, hmac
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=")
    head = b64(json.dumps(header or {"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = b64(hmac.new(secret.encode(), head + b"." + body, hashlib.sha256).digest())
    return (head + b"." + body + b"." + sig).decode()


def test_tokens_from_previous_version_still_valid_and_forged_ones_rejected():
    from app.config import JWT_SECRET_KEY
    from app.security import create_access_token, decode_access_token
    future = int(time.time()) + 3600
    old_style = _manual_hs256({"sub": "7", "username": "stary", "tv": 2, "exp": future}, JWT_SECRET_KEY)
    assert decode_access_token(old_style)["sub"] == "7"
    assert decode_access_token(create_access_token(7, "x", 2))["tv"] == 2
    assert decode_access_token(_manual_hs256({"sub": "7", "exp": future}, "iny-tajny-kluc")) is None
    assert decode_access_token(_manual_hs256({"sub": "7", "exp": int(time.time()) - 5}, JWT_SECRET_KEY)) is None
    assert decode_access_token(_manual_hs256({"sub": "7", "exp": future}, JWT_SECRET_KEY, header={"alg": "none", "typ": "JWT"})) is None
    assert decode_access_token(old_style[:-3] + "AAA") is None
    assert decode_access_token("nie-je-jwt") is None


@pytest.mark.parametrize("path", ["/api/forecast/history?symbol=%00", "/api/market/prices?ids=bit%00coin"])
def test_nul_in_url_or_query_is_rejected(registered, path):
    client, _u, _p = registered
    assert client.get(path).status_code == 400


def test_nul_in_json_body_is_rejected_in_every_form(registered):
    client, _u, _p = registered
    h = {**csrf_headers(client), "Content-Type": "application/json"}
    for raw in (rb'{"provider": "gem\u0000ini", "messages": [{"role": "user", "content": "x"}]}',
                b'{"provider": "gem\x00ini", "messages": []}'):
        assert client.post("/api/chat", content=raw, headers=h).status_code == 400
    assert client.post("/api/chat", content=b'{"provider":"a\x00b"}', headers=h).status_code in (400, 422)


def test_oversized_body_is_rejected_and_normal_body_still_works(registered):
    client, _u, _p = registered
    h = {**csrf_headers(client), "Content-Type": "application/json"}
    assert client.post("/api/chat", content=b'{"provider":"openai","messages":[],"pad":"' + b"x" * 1_100_000 + b'"}', headers=h).status_code == 413
    ok = client.post("/api/chat", json={"provider": "openai", "messages": [{"role": "user", "content": "ahoj"}]}, headers=csrf_headers(client))
    assert ok.status_code == 200 and ok.json()["success"] is True


def test_deepseek_call_disables_thinking_mode_and_uses_current_model(monkeypatch):
    from app.services import ai_engine
    from app.config import DEEPSEEK_MODEL
    assert DEEPSEEK_MODEL != "deepseek-chat"
    captured = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "OK"}}]}

    def fake_post(url, headers, payload, timeout):
        captured.update(url=url, payload=payload)
        return Resp()

    monkeypatch.setattr(ai_engine, "_post_with_retry", fake_post)
    ok, text, err = ai_engine.call_ai_provider("deepseek", "hi", "sk-test")
    assert ok and text == "OK"
    assert captured["payload"]["model"] == DEEPSEEK_MODEL
    assert captured["payload"].get("thinking") == {"type": "disabled"}


def test_grok_model_is_not_the_retired_grok2_alias():
    from app.config import GROK_MODEL
    assert GROK_MODEL != "grok-2-latest"


def test_gemini_model_is_current_generation():
    from app.config import GEMINI_MODEL
    assert GEMINI_MODEL not in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-pro")


def test_html_emails_escape_username():
    from app.services.email_service import render_lockout_email, render_reset_password_email, render_verification_email
    evil = "<img src=x onerror=alert(1)>"
    for fn, args in (
        (render_reset_password_email, (evil, "123456", 15)),
        (render_verification_email, (evil, "123456", 15)),
        (render_lockout_email, (evil, 15)),
    ):
        _text, html_body = fn(*args)
        assert "<img" not in html_body
        assert "&lt;img" in html_body and "&gt;" in html_body



def test_production_short_custom_secret_only_warns(monkeypatch, caplog):
    from app import config
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "PASSWORD_HASH_ROUNDS", 310_000)
    monkeypatch.setattr(config, "JWT_SECRET_KEY", "moj-vlastny-kratsi-kluc")
    monkeypatch.setattr(config, "API_KEY_ENCRYPTION_SECRET", "iny-vlastny-kluc-2024")
    config.validate_production_config()
    assert "kratsi nez 32 znakov" in caplog.text
