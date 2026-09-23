"""app/routers/chat.py — AI Crypto Assistant (plávajúce chat okno)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_CHAT
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import User
from app.rate_limit import rate_limit_by_user
from app.schemas import AIResultOut
from app.services.ai_engine import chat_with_ai

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    provider: str
    messages: List[ChatMessageIn]
    lang: str = "en"


@router.post("", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_CHAT))])
def send_chat_message(payload: ChatRequest, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> AIResultOut:
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    messages = [m.model_dump() for m in payload.messages]
    result = chat_with_ai(payload.provider, messages, api_key, payload.lang)
    return AIResultOut(**result.as_dict())
