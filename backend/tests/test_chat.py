"""Testy pre app/routers/chat.py — AI chat asistent (mock rezim)."""

from tests.conftest import anon_csrf_headers, csrf_headers


def test_chat_requires_auth(client):
    res = client.post("/api/chat", json={"provider": "gemini", "messages": [{"role": "user", "content": "hi"}]},
                       headers=anon_csrf_headers(client))
    assert res.status_code == 401


def test_chat_without_api_key_returns_mock_reply(registered):
    client, _username, _password = registered
    payload = {"provider": "gemini", "messages": [{"role": "user", "content": "What is Bitcoin?"}], "lang": "en"}
    res = client.post("/api/chat", json=payload, headers=csrf_headers(client))
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["is_mock"] is True
    assert "reply" in body["data"]
    assert "SAMPLE DATA" in body["data"]["reply"]


def test_chat_empty_messages_reports_failure(registered):
    client, _username, _password = registered
    res = client.post("/api/chat", json={"provider": "gemini", "messages": []}, headers=csrf_headers(client))
    assert res.status_code == 200
    assert res.json()["success"] is False
