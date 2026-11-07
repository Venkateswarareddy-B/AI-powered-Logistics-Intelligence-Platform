"""Agentic AI API endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from agents.agent import run_agent

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentRequest(BaseModel):
    request: str


@router.post("/run")
def agent_run(
    req: AgentRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Run the logistics agent for a user request.

    The agent calls real tools to retrieve live data, then generates
    a recommendation with transparent tool execution summary.
    """
    return run_agent(db, req.request, user_id=user["user_id"])
