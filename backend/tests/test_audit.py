"""Account activity log and new-device login alerts."""

from tests.conftest import anon_csrf_headers, csrf_headers

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"


def _login(client, username, password, user_agent=CHROME_WIN):
    headers = {**anon_csrf_headers(client), "User-Agent": user_agent}
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=headers)


def _actions(client):
    return [e["action"] for e in client.get("/api/account/activity").json()["events"]]


def test_activity_requires_auth(client):
    assert client.get("/api/account/activity").status_code == 401


def test_register_and_login_are_logged_newest_first(registered):
    client, username, password = registered
    assert _login(client, username, password).status_code == 200
    actions = _actions(client)
    assert actions[:2] == ["login_success", "register"]


def test_failed_login_and_lockout_are_logged(registered):
    client, username, password = registered
    for _ in range(5):
        _login(client, username, "wrong-password")
    from app.database import SessionLocal
    from app.models import AuditEvent
    with SessionLocal() as db:
        actions = [row.action for row in db.query(AuditEvent).order_by(AuditEvent.id).all()]
    assert actions.count("login_failed") == 5 and actions[-1] == "account_locked"


def test_sensitive_account_changes_are_logged(registered):
    client, _username, password = registered
    client.post("/api/account/change-password", json={"current_password": password, "new_password": "NewPass12345"},
                headers=csrf_headers(client))
    client.put("/api/account/api-keys", json={"provider": "gemini", "api_key": "AIza-test-1234"},
               headers=csrf_headers(client))
    client.delete("/api/account/api-keys/gemini", headers=csrf_headers(client))
    client.post("/api/account/logout-all-devices", headers=csrf_headers(client))
    actions = _actions(client)
    assert actions[:4] == ["logout_all", "api_key_deleted", "api_key_saved", "password_changed"]
    event = client.get("/api/account/activity").json()["events"][1]
    assert event["details"] == "gemini" and event["created_at"].endswith("+00:00")


def test_failed_change_is_not_logged(registered):
    client, _username, _password = registered
    res = client.post("/api/account/change-password", json={"current_password": "bad", "new_password": "NewPass12345"},
                      headers=csrf_headers(client))
    assert res.status_code == 400
    assert "password_changed" not in _actions(client)


def test_activity_is_private_to_each_user(registered):
    client, _username, _password = registered
    client.post("/api/auth/logout", headers=csrf_headers(client))
    client.cookies.clear()
    res = client.post("/api/auth/register", json={"username": "otheruser", "password": "OtherPass123",
                                                    "email": "other@example.com"}, headers=anon_csrf_headers(client))
    assert res.status_code == 201
    assert _actions(client) == ["register"]


def test_log_is_pruned_per_user(registered, monkeypatch):
    from app.services import audit
    monkeypatch.setattr(audit, "MAX_EVENTS_PER_USER", 3)
    client, username, password = registered
    for _ in range(4):
        _login(client, username, password)
    assert len(client.get("/api/account/activity?limit=200").json()["events"]) == 3


def test_describe_user_agent():
    from app.services.audit import describe_user_agent
    assert describe_user_agent(CHROME_WIN) == "Chrome (Windows)"
    assert describe_user_agent(FIREFOX_LINUX) == "Firefox (Linux)"
    assert describe_user_agent(None) == "Unknown device"


def _capture_emails(monkeypatch):
    from app.routers import auth
    sent = []
    monkeypatch.setattr(auth, "is_email_configured", lambda: True)
    monkeypatch.setattr(auth, "send_email", lambda to, subject, text, html=None: sent.append((to, subject, text)))
    return sent


def test_new_device_login_sends_alert_once(registered, monkeypatch):
    client, username, password = registered
    sent = _capture_emails(monkeypatch)
    assert _login(client, username, password, CHROME_WIN).status_code == 200
    assert _login(client, username, password, FIREFOX_LINUX).status_code == 200
    assert len(sent) == 2  # testclient registered with its own user agent, so both browsers are new
    assert "Firefox (Linux)" in sent[-1][2] and sent[-1][0] == "testuser1@example.com"
    _login(client, username, password, FIREFOX_LINUX)
    _login(client, username, password, CHROME_WIN)
    assert len(sent) == 2


def test_known_device_login_sends_no_alert(registered, monkeypatch):
    client, username, password = registered
    sent = _capture_emails(monkeypatch)
    _login(client, username, password, user_agent="testclient")
    assert sent == []
