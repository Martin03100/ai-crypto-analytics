"""Request guard middleware."""

from __future__ import annotations

import json
import re

MAX_BODY_BYTES = 1_000_000
_NUL_ESCAPE = re.compile(rb"\\u0000", re.IGNORECASE)
_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def _respond(send, status: int, detail: str) -> None:
    payload = json.dumps({"detail": detail}).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
    await send({"type": "http.response.body", "body": payload})


class RequestGuardMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_target = scope.get("raw_path", b"") + b"?" + scope.get("query_string", b"")
        if b"\x00" in raw_target or b"%00" in raw_target.lower():
            await _respond(send, 400, "Neplatný znak v požiadavke.")
            return

        if scope["method"] not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return

        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            await _respond(send, 413, "Požiadavka je príliš veľká.")
            return

        messages, size = [], 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > MAX_BODY_BYTES:
                await _respond(send, 413, "Požiadavka je príliš veľká.")
                return
            if not message.get("more_body", False):
                break

        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.request")
        if b"\x00" in body or _NUL_ESCAPE.search(body):
            await _respond(send, 400, "Neplatný znak v požiadavke.")
            return

        replay = iter(messages)

        async def replayed_receive():
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        await self.app(scope, replayed_receive, send)
