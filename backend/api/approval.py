"""Human Approval & Audit API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.services.approval_service import (
    create_approval_request, process_decision,
    list_audit_logs, list_pending_approvals, list_all_approvals,
)

router = APIRouter(prefix="/api", tags=["approval"])


class CreateApprovalReq(BaseModel):
    agent_decision_id: str | None = None
    shipment_id: str | None = None
    action_type: str = "ROUTE_CHANGE"
    recommendation_summary: str
    supporting_evidence: str | None = None
    estimated_time_saving_hours: float | None = None
    estimated_cost_impact: float | None = None
    estimated_risk_reduction_pct: float | None = None


class DecisionReq(BaseModel):
    decision: str  # APPROVED | REJECTED | MORE_INFO_REQUESTED
    decision_reason: str | None = None


@router.get("/approvals")
def get_approvals(status: str | None = None, db: Session = Depends(get_db),
                  _=Depends(get_current_user)):
    if status == "PENDING":
        return list_pending_approvals(db)
    return list_all_approvals(db)


@router.post("/approvals")
def create_approval(
    req: CreateApprovalReq,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    approval_id = create_approval_request(
        db,
        agent_decision_id=req.agent_decision_id,
        shipment_id=req.shipment_id,
        action_type=req.action_type,
        recommendation_summary=req.recommendation_summary,
        supporting_evidence=req.supporting_evidence,
        requested_by=user["user_id"],
        estimated_time_saving_hours=req.estimated_time_saving_hours,
        estimated_cost_impact=req.estimated_cost_impact,
        estimated_risk_reduction_pct=req.estimated_risk_reduction_pct,
    )
    return {"approval_id": approval_id, "status": "PENDING"}


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    req: DecisionReq,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = process_decision(db, approval_id, req.decision, user["user_id"], req.decision_reason)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/audit")
def get_audit_logs(
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return list_audit_logs(db, entity_type=entity_type, action=action, limit=limit)
