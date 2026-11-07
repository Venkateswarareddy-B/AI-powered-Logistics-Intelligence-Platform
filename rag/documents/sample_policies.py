"""Sample policy document creation for YottaFlex demo environment.

Creates clearly-labelled fictional company policies. Never claims these
are actual company policies.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

import uuid

SAMPLE_POLICIES = [
    {
        "document_name": "SLA Policy",
        "category": "SLA_POLICY",
        "content": """YottaFlex SLA Policy (Fictional — DEMO DATA)

1. Service Level Definitions
   - STANDARD: Maximum delivery within 48 hours. Allowed delay: 4 hours.
   - EXPRESS: Maximum delivery within 24 hours. Allowed delay: 2 hours.
   - SAME_DAY: Maximum delivery within 8 hours. Allowed delay: 1 hour.
   - PRIORITY: Maximum delivery within 12 hours. Allowed delay: 1.5 hours.

2. SLA Status Classification
   - ON_TIME: Predicted or actual delivery within promised time.
   - AT_RISK: Predicted delivery exceeds promised time but within allowed delay window.
   - BREACHED: Predicted or actual delivery exceeds promised time + allowed delay.

3. Escalation Triggers
   - AT_RISK status must be reviewed within 2 hours.
   - BREACHED status must be escalated to Operations Manager immediately.
   - Three consecutive BREACHED shipments for a carrier triggers carrier review.

4. Reporting
   - SLA compliance percentage is calculated as: (ON_TIME / Total) * 100.
   - Daily SLA reports must be generated before 09:00 local time.

5. Customer Communication
   - AT_RISK: Notify customer of potential delay.
   - BREACHED: Issue formal delay notification with revised ETA.
   - Critical BREACHED (>24h delay): Escalate to account manager for compensation review.
""",
    },
    {
        "document_name": "Carrier Policy",
        "category": "CARRIER_POLICY",
        "content": """YottaFlex Carrier Policy (Fictional — DEMO DATA)

1. Carrier Onboarding
   - All carriers must pass a 30-day evaluation period.
   - Minimum acceptable on-time rate: 85%.
   - Carriers below 70% on-time rate for 7 consecutive days are suspended.

2. Carrier Score Formula
   - carrier_score = 40 * on_time_rate + 30 * (1 - late_scan_rate) + 30 * (1 - min(avg_delay/24, 1))
   - Score range: 0-100. Higher is better.

3. Carrier Review Process
   - Monthly performance reviews are mandatory.
   - Carriers with score < 50 are placed on probation.
   - Carriers with score < 30 for two consecutive months are terminated.

4. Route Change Authorization
   - Carriers may not change routes without prior approval.
   - Route changes must be documented with reason and approval ID.

5. Late Scan Management
   - Late scan rate > 15% triggers automated alert.
   - Late scan rate > 25% requires carrier contact.
""",
    },
    {
        "document_name": "Weather SOP",
        "category": "WEATHER_SOP",
        "content": """YottaFlex Weather Standard Operating Procedure (Fictional — DEMO DATA)

1. Weather Impact Assessment
   - NORMAL (factor 1.0): No action required.
   - RAIN (factor 1.15): Monitor affected shipments. Add 15% to transit estimates.
   - HEAVY_RAIN (factor 1.35): Issue delay alerts. Consider route alternatives.
   - STORM (factor 1.60): Activate contingency plans. Notify affected customers.
   - FLOOD (factor 2.00): Suspend operations in affected areas. Escalate to Manager.
   - EXTREME_HEAT (factor 1.10): Monitor temperature-sensitive cargo.
   - FOG (factor 1.25): Reduce dispatch frequency. Add 25% to transit estimates.

2. Weather Alert Protocol
   - Severity 1-2: Log and monitor.
   - Severity 3: Notify Operations team and affected carriers.
   - Severity 4: Escalate to Operations Manager. Suspend shipments if needed.

3. Post-Weather Recovery
   - After weather event ends, reassess all delayed shipments within 1 hour.
   - Generate weather impact report within 4 hours of event end.
""",
    },
    {
        "document_name": "Facility SOP",
        "category": "FACILITY_SOP",
        "content": """YottaFlex Facility Standard Operating Procedure (Fictional — DEMO DATA)

1. Congestion Management
   - Utilization < 60%: Normal operations.
   - Utilization 60-80%: Monitor closely. Increase processing staff if possible.
   - Utilization 80-90%: Issue congestion alert. Consider diverting shipments.
   - Utilization > 90%: Critical. Divert new shipments to alternative facilities.

2. Queue Processing
   - Average processing time should not exceed 30 minutes per shipment.
   - Facilities with > 45 min average processing time require review.
   - Priority shipments (HIGH/CRITICAL) must be processed within 15 minutes.

3. Facility Performance Review
   - Weekly utilization reports are mandatory.
   - Facilities with > 75% average utilization for 7 days require capacity review.
   - Delay contribution rate > 30% triggers operational audit.
""",
    },
    {
        "document_name": "Delay Handling Policy",
        "category": "DELAY_HANDLING",
        "content": """YottaFlex Delay Handling Policy (Fictional — DEMO DATA)

1. Delay Classification
   - Minor delay: 0-2 hours beyond promised time.
   - Moderate delay: 2-6 hours beyond promised time.
   - Major delay: 6-24 hours beyond promised time.
   - Critical delay: > 24 hours beyond promised time.

2. Delay Response Protocol
   - Minor: Log and monitor. No customer notification required.
   - Moderate: Notify customer. Assign root cause within 4 hours.
   - Major: Escalate to Operations Manager. Customer compensation review.
   - Critical: Executive escalation. Mandatory root cause analysis within 24 hours.

3. Root Cause Categories
   WEATHER, FACILITY_CONGESTION, CARRIER_ISSUE, ROUTE_CHANGE, CUSTOMS,
   MECHANICAL, TRAFFIC, DEMAND_SURGE, MISSING_SCAN, OTHER.

4. Delay Prevention
   - Use ETA predictions to proactively identify at-risk shipments.
   - If delay probability > 70%, generate HIGH_DELAY_RISK alert.
   - Recommend alternative routes when weather or congestion is detected.

5. Delay Explanation (Explainable AI)
   - Every delay prediction must include a SHAP-based explanation.
   - Explanation shows top factors contributing to delay probability.
   - Format: "Heavy rain: +28 percentage points, Facility queue: +21 percentage points"
   - Explanations must be derived from actual SHAP values, not fabricated.
""",
    },
    {
        "document_name": "Route Change Policy",
        "category": "ROUTE_CHANGE",
        "content": """YottaFlex Route Change Policy (Fictional — DEMO DATA)

1. Route Change Authorization
   - Route changes require Operations Manager approval.
   - Emergency route changes (weather, accident) may be pre-approved with post-notification.
   - All route changes must be recorded with: original route, new route, reason, approver.

2. What-If Analysis Requirements
   - Before approving a route change, compare:
     * Estimated delivery time (current vs alternative)
     * Delay probability (current vs alternative)
     * Additional cost
     * Risk reduction
   - The recommended route must show net benefit (time saved or risk reduced).
   - Cost estimate: Rs 8/km (documented simulation rule, not verified carrier quotation).

3. Route Change Limits
   - Maximum 2 route changes per shipment.
   - Route changes within 4 hours of promised delivery require Manager approval.
   - Cost increase > 20% requires Finance approval.
""",
    },
    {
        "document_name": "Escalation Policy",
        "category": "ESCALATION",
        "content": """YottaFlex Escalation Policy (Fictional — DEMO DATA)

1. Escalation Levels
   - Level 1 (Operator): Minor delays, single shipment issues.
   - Level 2 (Planner): Moderate delays, multi-shipment issues, route changes.
   - Level 3 (Manager): Major delays, SLA breaches, carrier performance issues.
   - Level 4 (Director): Critical delays, systemic failures, customer escalation.

2. Escalation Triggers
   - SLA BREACHED: Escalate to Level 3 immediately.
   - 3+ shipments BREACHED same day same carrier: Escalate to Level 4.
   - Weather severity 4 (FLOOD): Escalate to Level 3.
   - Facility utilization > 95%: Escalate to Level 2.

3. Response Time SLAs
   - Level 1: 2 hours
   - Level 2: 1 hour
   - Level 3: 30 minutes
   - Level 4: 15 minutes

4. Documentation
   - All escalations must be logged in the audit trail.
   - Include: trigger, shipment IDs, action taken, approver, timestamp.

5. Human Approval Workflow
   - Sensitive operational actions require human approval.
   - Decision options: APPROVE, REJECT, REQUEST MORE INFORMATION.
   - All decisions are logged in immutable audit_logs.
""",
    },
    {
        "document_name": "Data Quality Policy",
        "category": "OTHER",
        "content": """YottaFlex Data Quality Policy (Fictional — DEMO DATA)

1. Anomaly Detection
   - All tracking events are validated for: PK uniqueness, FK integrity, enum values,
     date consistency, shipment lifecycle, duplicate events, delayed scans, future events.
   - Anomalies are labelled and preserved — never silently deleted.

2. Ground Truth
   - Ground truth labels are generated by the synthetic data generator.
   - Ground truth must NEVER be used as an ML model input feature.
   - Ground truth is stored separately in data_quality_issues.ground_truth_label.

3. Future Data Leakage Prevention
   - For a prediction at time T, only events with ingestion_time <= T are used.
   - feature_cutoff_time <= prediction_time is enforced by DB check constraint.
   - Time-aware train/validation splits prevent temporal leakage.

4. Validation Summary
   - validation_summary.json is generated after each data generation run.
   - Includes: row counts, duplicate counts, FK errors, anomaly counts, checksums.
   - Same seed + same parameters = identical checksums (reproducibility).
""",
    },
]


def seed_sample_policies(db: Session, created_by: str | None = None) -> int:
    """Create sample policy documents in the database.

    Returns the number of documents created.
    """
    now = datetime.now(timezone.utc)
    count = 0

    for policy in SAMPLE_POLICIES:
        doc_id = f"RAGDOC-{policy['category']}-{uuid.uuid4().hex[:8].upper()}"

        # Check if a document with this name already exists
        existing = db.execute(text(
            "SELECT document_id FROM rag_documents WHERE document_name = :name AND is_active = TRUE"
        ), {"name": policy["document_name"]}).scalar()

        if existing:
            continue  # skip if already exists

        db.execute(text("""
            INSERT INTO rag_documents (
                document_id, document_name, category, version,
                content_text, file_type,
                processing_status, is_active, is_demo,
                created_by, description, created_at, updated_at
            ) VALUES (
                :did, :dname, :cat, '1.0',
                :content, 'TEXT',
                'PENDING', TRUE, TRUE,
                :cby, 'DEMO DATA — fictional sample policy', :now, :now
            ) ON CONFLICT (document_id) DO NOTHING
        """), {
            "did": doc_id,
            "dname": policy["document_name"],
            "cat": policy["category"],
            "content": policy["content"],
            "cby": created_by,
            "now": now,
        })
        count += 1

    db.commit()
    return count
