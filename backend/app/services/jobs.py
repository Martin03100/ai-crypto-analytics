"""Background AI jobs.

AI providers can take longer than the ~26 s the Netlify /api proxy allows for one request. A client that sends
`Prefer: respond-async` gets `202 {"job_id": ...}` straight away and polls GET /api/jobs/{id} for the result, so
no single HTTP request has to wait for the model.

Jobs live in this process's memory (like the rate limits): exact for one backend instance, lost on restart.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("aca.jobs")

JOB_TTL_SECONDS = 15 * 60
MAX_RUNNING_PER_USER = 4
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ai-job")
_lock = threading.Lock()


@dataclass
class Job:
    user_id: int
    created: float = field(default_factory=time.monotonic)
    done: bool = False
    result: Optional[Dict[str, Any]] = None


_jobs: Dict[str, Job] = {}


def _prune(now: float) -> None:
    for job_id in [k for k, j in _jobs.items() if now - j.created > JOB_TTL_SECONDS]:
        del _jobs[job_id]


def submit(user_id: int, compute: Callable[[], Dict[str, Any]]) -> str:
    now = time.monotonic()
    with _lock:
        _prune(now)
        running = sum(1 for j in _jobs.values() if j.user_id == user_id and not j.done)
        if running >= MAX_RUNNING_PER_USER:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Príliš veľa požiadaviek. Skús to znova o 10s.", headers={"Retry-After": "10"})
        job_id = secrets.token_urlsafe(16)
        job = _jobs[job_id] = Job(user_id=user_id)

    def run() -> None:
        try:
            result = compute()
        except Exception as exc:  # noqa: BLE001 - the client must always get an answer
            logger.error("AI uloha zlyhala: %s", exc, exc_info=exc)
            result = {"success": False, "data": None, "is_mock": False,
                      "error_message": "Nastala neočakávaná chyba na serveri.", "provider_used": None}
        with _lock:
            job.result, job.done = result, True

    _executor.submit(run)
    return job_id


def get(user_id: int, job_id: str) -> Optional[Job]:
    """The job if it exists and belongs to this user (another user's id behaves like an unknown one)."""
    with _lock:
        job = _jobs.get(job_id)
        return job if job is not None and job.user_id == user_id else None


def wants_async(request: Request) -> bool:
    return request.headers.get("prefer", "").lower().startswith("respond-async")


def respond(request: Request, user_id: int, compute: Callable[[], Dict[str, Any]]):
    """Run `compute` in the background for async clients (202 + job id), inline for everyone else."""
    if wants_async(request):
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"job_id": submit(user_id, compute)})
    return compute()
