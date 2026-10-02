"""Polling endpoint for background AI jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from app.deps import get_current_user
from app.models import User
from app.services import jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str = Path(min_length=16, max_length=32, pattern=r"^[A-Za-z0-9_-]+$"),
               user: User = Depends(get_current_user)) -> dict:
    job = jobs.get(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Úloha neexistuje alebo už vypršala.")
    return {"status": "done", "result": job.result} if job.done else {"status": "running"}
