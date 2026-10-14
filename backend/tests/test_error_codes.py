"""Every error message a user can see carries a stable code the app translates (app.error_codes)."""

import pathlib
import re

from app import error_codes
from tests.conftest import anon_csrf_headers

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
# Not shown to users of the app: machine-to-machine answers and the admin's own tools.
IGNORED = (re.compile(r"^Not found$"), re.compile(r"^Invalid (signature|payload)\.$"), re.compile("ADMIN_USERNAMES"),
           re.compile(r"^Stripe ", re.IGNORECASE))


def _details():
    found = set()
    for path in APP.rglob("*.py"):
        for match in re.finditer(r'detail=f?"((?:[^"\\]|\\.)+)"', path.read_text(encoding="utf-8")):
            found.add(re.sub(r"\{[^}]*\}", "5", match.group(1)))      # f-string fields become a sample number
    return sorted(d for d in found if not any(p.search(d) for p in IGNORED))


def test_every_error_message_in_the_source_has_a_code():
    details = _details()
    assert len(details) > 60
    assert [d for d in details if error_codes.lookup(d) is None] == []


def test_numbers_in_a_message_become_params():
    assert error_codes.lookup("Môžeš mať najviac 25 aktívnych alarmov.") == ("alertLimit", {"max": "25"})
    assert error_codes.lookup("some text from an AI provider") is None


def test_error_responses_carry_the_code(client):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "WrongPass123"},
                      headers=anon_csrf_headers(client))
    assert res.status_code == 401 and res.json()["code"] == "invalidCredentials"
    res = client.post("/api/auth/logout")                      # no CSRF token
    assert res.status_code == 403 and res.json()["code"] == "csrfInvalid"
