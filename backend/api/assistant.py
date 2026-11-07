"""GenAI assistant API endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from genai.assistant.chat import chat as ai_chat

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def assistant_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Send a question to the YottaFlex AI assistant.

    Returns a grounded response based on live PostgreSQL data.
    If Groq is not configured, returns a configuration message.
    """
    return ai_chat(db, req.message)
