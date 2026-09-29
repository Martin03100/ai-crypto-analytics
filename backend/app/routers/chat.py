"""AI chat API."""

from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_CHAT
from app.deps import get_current_user, get_db, get_decrypted_api_key
from app.models import User
from app.rate_limit import rate_limit_by_user
from app.schemas import AIResultOut
from app.services.ai_engine import chat_with_ai

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    provider: str = Field(max_length=32)
    messages: List[ChatMessageIn] = Field(max_length=200)
    lang: str = "en"


@router.post("", response_model=AIResultOut, dependencies=[Depends(rate_limit_by_user(*RATE_LIMIT_CHAT))])
def send_chat_message(payload: ChatRequest, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> AIResultOut:
    api_key = get_decrypted_api_key(db, user.id, payload.provider)
    messages = [
        {**m.model_dump(), "content": str(m.content)[:4000]}
        for m in payload.messages[-20:]
    ]
    result = chat_with_ai(payload.provider, messages, api_key, payload.lang)
    return AIResultOut(**result.as_dict())
