"""Human Approval & Audit Service (Phase 20).

Handles:
  1. Creating approval requests for sensitive operational actions.
  2. Processing approve / reject / request-more-info decisions.
  3. Recording every decision in audit_logs (immutable).
  4. Linking approvals to agent_decisions.
  5. Providing audit history queries.

Never automatically executes sensitive operational actions without approval.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("backend.services.approval_service")


def create_approval_request(
    db: Session,
    agent_decision_id: str | None = None,
    shipment_id: str | None = None,
    action_type: str = "ROUTE_CHANGE",
    recommendation_summary: str = "",
    supporting_evidence: str | None = None,
    requested_by: str | None = None,
    model_version: str | None = None,
    estimated_time_saving_hours: float | None = None,
    estimated_cost_impact: float | None = None,
    estimated_risk_reduction_pct: float | None = None,
) -> str:
    """Create a new human approval request. Returns the approval_id."""
    import uuid
    approval_id = f"APR-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)

    db.execute(text("""
        INSERT INTO human_approvals (
            approval_id, agent_decision_id, shipment_id,
            action_type, recommendation_summary, supporting_evidence,
            requested_by, status,
            model_version,
            estimated_time_saving_hours, estimated_cost_impact,
            estimated_risk_reduction_pct,
            created_at, updated_at
        ) VALUES (
            :aid, :adid, :sid,
            :atype, :summary, :evidence,
            :rby, 'PENDING',
            :mv,
            :ts, :ci, :rr,
            :now, :now
        ) ON CONFLICT (approval_id) DO NOTHING
    """), {
        "aid": approval_id, "adid": agent_decision_id, "sid": shipment_id,
        "atype": action_type, "summary": recommendation_summary,
        "evidence": supporting_evidence,
        "rby": requested_by,
        "mv": model_version,
        "ts": estimated_time_saving_hours,
        "ci": estimated_cost_impact,
        "rr": estimated_risk_reduction_pct,
        "now": now,
    })

    # Audit log: approval requested
    _audit_log(db, user_id=requested_by, action="APPROVAL_REQUESTED",
               entity_type="HumanApproval", entity_id=approval_id,
               decision="PENDING", reason=recommendation_summary,
               model_version=model_version)

    db.commit()
    log.info("approval request created: %s (action=%s)", approval_id, action_type)
    return approval_id


def process_decision(
    db: Session,
    approval_id: str,
    decision: str,
    decided_by: str,
    decision_reason: str | None = None,
) -> dict:
    """Process an approve/reject/request-more-info decision.

    Args:
        approval_id: The approval to decide on.
        decision: APPROVED | REJECTED | MORE_INFO_REQUESTED
        decided_by: User ID of the approver.
        decision_reason: Optional reason text.

    Returns:
        Dict with status and audit info.
    """
    valid_decisions = {"APPROVED", "REJECTED", "MORE_INFO_REQUESTED"}
    if decision not in valid_decisions:
        return {"error": f"Invalid decision: {decision}. Must be one of {valid_decisions}"}

    row = db.execute(text("""
        SELECT approval_id, status, shipment_id, agent_decision_id,
               action_type, recommendation_summary, model_version
        FROM human_approvals WHERE approval_id = :aid
    """), {"aid": approval_id}).mappings().fetchone()

    if not row:
        return {"error": f"Approval {approval_id} not found"}

    row = dict(row)
    if row["status"] != "PENDING":
        return {"error": f"Approval {approval_id} is already {row['status']}"}

    now = datetime.now(timezone.utc)

    # Update approval record
    db.execute(text("""
        UPDATE human_approvals
        SET status = :decision, decided_by = :uid,
            decision_reason = :reason, decided_at = :now,
            updated_at = :now
        WHERE approval_id = :aid
    """), {
        "decision": decision, "uid": decided_by,
        "reason": decision_reason, "now": now, "aid": approval_id,
    })

    # Update agent decision if linked
    if row["agent_decision_id"]:
        agent_status = "APPROVED" if decision == "APPROVED" else "REJECTED"
        db.execute(text("""
            UPDATE agent_decisions
            SET approval_status = :status, approved_by = :uid, updated_at = :now
            WHERE agent_decision_id = :aid
        """), {
            "status": agent_status, "uid": decided_by,
            "now": now, "aid": row["agent_decision_id"],
        })

    # Audit log the decision (immutable)
    _audit_log(
        db, user_id=decided_by,
        action=f"APPROVAL_{decision}",
        entity_type="HumanApproval", entity_id=approval_id,
        decision=decision,
        reason=decision_reason or row["recommendation_summary"],
        model_version=row.get("model_version"),
        extra={"shipment_id": row.get("shipment_id"), "action_type": row.get("action_type")},
    )

    db.commit()
    log.info("approval %s decided: %s by %s", approval_id, decision, decided_by)

    return {
        "approval_id": approval_id,
        "decision": decision,
        "decided_by": decided_by,
        "decided_at": now.isoformat(),
        "shipment_id": row.get("shipment_id"),
        "action_type": row.get("action_type"),
    }


def _audit_log(
    db: Session,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    decision: str | None = None,
    reason: str | None = None,
    model_version: str | None = None,
    extra: dict | None = None,
) -> str:
    """Write an immutable audit log entry. Returns the audit_id."""
    import uuid
    audit_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)

    db.execute(text("""
        INSERT INTO audit_logs (
            audit_id, user_id, action, entity_type, entity_id,
            decision, reason, model_version, extra_data, timestamp
        ) VALUES (
            :aid, :uid, :action, :etype, :eid,
            :decision, :reason, :mv, :extra, :now
        ) ON CONFLICT (audit_id) DO NOTHING
    """), {
        "aid": audit_id, "uid": user_id,
        "action": action, "etype": entity_type, "eid": entity_id,
        "decision": decision, "reason": reason,
        "mv": model_version,
        "extra": json.dumps(extra) if extra else None,
        "now": now,
    })
    return audit_id


def list_audit_logs(
    db: Session,
    entity_type: str | None = None,
    action: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query audit history with optional filters."""
    filters, params = [], {"limit": limit}
    if entity_type: filters.append("entity_type=:et"); params["et"] = entity_type
    if action:     filters.append("action=:act");        params["act"] = action
    if user_id:    filters.append("user_id=:uid");       params["uid"] = user_id
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    rows = db.execute(text(f"""
        SELECT audit_id, user_id, action, entity_type, entity_id,
               decision, reason, model_version, extra_data, timestamp
        FROM audit_logs {where}
        ORDER BY timestamp DESC
        LIMIT :limit
    """), params).mappings().fetchall()
    return [dict(r) for r in rows]


def list_pending_approvals(db: Session, limit: int = 50) -> list[dict]:
    """List all pending approval requests."""
    rows = db.execute(text("""
        SELECT ha.approval_id, ha.agent_decision_id, ha.shipment_id,
               ha.action_type, ha.recommendation_summary,
               ha.estimated_time_saving_hours, ha.estimated_cost_impact,
               ha.estimated_risk_reduction_pct,
               ha.created_at, ha.requested_by,
               s.status AS shipment_status
        FROM human_approvals ha
        LEFT JOIN shipments s ON ha.shipment_id = s.shipment_id
        WHERE ha.status = 'PENDING'
        ORDER BY ha.created_at DESC
        LIMIT :limit
    """), {"limit": limit}).mappings().fetchall()
    return [dict(r) for r in rows]


def list_all_approvals(db: Session, limit: int = 100) -> list[dict]:
    """List all approvals (all statuses)."""
    rows = db.execute(text("""
        SELECT * FROM human_approvals
        ORDER BY created_at DESC LIMIT :limit
    """), {"limit": limit}).mappings().fetchall()
    return [dict(r) for r in rows]
