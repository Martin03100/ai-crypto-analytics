"""
tests/conftest.py
===================
Spolocne pytest fixtures pre testy routerov (FastAPI TestClient).

DOLEZITE poradie: DATABASE_URL (teda cielovy SQLite subor pre testy) sa
MUSI nastavit PRED prvym importom cohokolvek z `app.*` — `app/config.py`
cita DATABASE_URL z env premennej uz pri importe modulu. Preto sa to deje
na samom zaciatku tohto suboru, este pred `from app.main import app`.
Vdaka tomu testy nikdy nezasahuju do skutocnej vyvojarskej databazy
(`backend/data/app.db`) a kazdy test zacina s cistymi tabulkami.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "aca_test.db")
if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("API_KEY_ENCRYPTION_SECRET", "test-only-fernet-secret-do-not-use-in-prod")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.rate_limit import _hits as _rate_limit_hits  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate limiter drzi stav v module-level dict (viz app/rate_limit.py) -
    zdielanom naprieč VSETKYMI testami v tomto procese, nie len v ramci
    jedneho testu/DB. Bez tohto resetu by testy neskor v sade zacali
    dostavat 429 namiesto ocakavaneho statusu, len preto, ze predchadzajuce
    testy "minuli" spolocny limit na /auth/login a pod. (realne to zaroven
    potvrdzuje, ze rate limiter naozaj funguje)."""
    _rate_limit_hits.clear()
    yield
    _rate_limit_hits.clear()


@pytest.fixture()
def client():
    """Testovaci HTTP klient s cistou databazou pre kazdy test — tabulky
    sa pred kazdym testom zahodia a znova vytvoria, takze testy sa navzajom
    neovplyvnuju bez ohladu na poradie spustenia."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def registered(client):
    """Zaregistruje testovacieho pouzivatela. TestClient si po tomto
    volani drzi session aj CSRF cookies pre dalsie requesty v ramci
    testu (rovnako ako prehliadac). Vracia (client, username, password)."""
    username = "testuser1"
    password = "TestPass123"
    res = client.post("/api/auth/register", json={"username": username, "password": password})
    assert res.status_code == 201, res.text
    return client, username, password


def csrf_headers(client) -> dict:
    """Vrati {"X-CSRF-Token": ...} z aktualne ulozenej CSRF cookie v
    klientovi — potrebne pre kazdy mutacny (POST/PUT/DELETE) request
    mimo /auth/login a /auth/register."""
    token = client.cookies.get("aca_csrf")
    return {"X-CSRF-Token": token} if token else {}


def anon_csrf_headers(client) -> dict:
    """Pre testy 'vyzaduje prihlasenie' na MUTACNYCH (POST/PUT/DELETE)
    endpointoch: CSRF middleware beh predtym nez sa vobec dostane k
    autentifikacii, takze uplne "holy" request (ziadne cookies) dostane
    403 (chybajuci CSRF token), nie 401. Aby test naozaj overil "vyzaduje
    prihlasenie" (401), musi najprv ako anonymny navstevnik ziskat CSRF
    cookie (GET request), a az s tou poslat POST/PUT/DELETE bez prihlasenia."""
    client.get("/api/health")
    return csrf_headers(client)
