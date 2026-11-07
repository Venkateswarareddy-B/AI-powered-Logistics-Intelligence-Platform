"""GenAI logistics assistant — answers operational questions using live DB data.

Workflow:
1. Parse the user's question.
2. If it mentions a shipment ID, retrieve live shipment data from PostgreSQL.
3. If it asks about carriers/facilities/delays, query the relevant tables.
4. Build a context string from the retrieved data.
5. Send the question + context to the Groq LLM.
6. Return the grounded response with data sources.

The LLM must NOT invent operational data. All values come from PostgreSQL.
If Groq is not configured, return a clear configuration message.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from genai.llm.provider import get_llm
from genai.prompts.system import SYSTEM_PROMPT

settings = get_settings()
log = logging.getLogger("genai.assistant.chat")

# Regex to find shipment IDs in user questions
_SHIPMENT_PATTERN = re.compile(r"SHP-\d{4}-\d{6}", re.IGNORECASE)


def _is_configured() -> bool:
    return settings.GROQ_ENABLED and bool(settings.GROQ_API_KEY)


def _config_message() -> dict:
    return {
        "response": (
            "The GenAI assistant requires a Groq API key to function. "
            "To enable this feature:\n\n"
            "1. Get a free key from https://console.groq.com/keys\n"
            "2. Set GROQ_API_KEY=your_key in your .env file\n"
            "3. Set GROQ_ENABLED=true in your .env file\n"
            "4. Restart the backend\n\n"
            "Until then, I can't generate AI responses. All other YottaFlex features work normally."
        ),
        "config_required": True,
        "model": settings.GROQ_MODEL,
    }


def _retrieve_shipment_context(db: Session, shipment_id: str) -> str:
    """Retrieve live shipment data from PostgreSQL for context."""
    parts = []

    # Shipment details
    row = db.execute(text("""
        SELECT s.shipment_id, s.status, s.sla_status, s.priority,
               s.planned_ship_time, s.promised_delivery_time, s.actual_delivery_time,
               c.carrier_name, sl.name AS service_level, r.route_name,
               fo.facility_name AS origin, fd.facility_name AS destination
        FROM shipments s
        JOIN carriers c ON s.carrier_id = c.carrier_id
        JOIN service_levels sl ON s.service_level_id = sl.service_level_id
        JOIN routes r ON s.route_id = r.route_id
        JOIN facilities fo ON s.origin_facility_id = fo.facility_id
        JOIN facilities fd ON s.destination_facility_id = fd.facility_id
        WHERE s.shipment_id = :sid
    """), {"sid": shipment_id}).mappings().fetchone()

    if row:
        r = dict(row)
        parts.append(f"Shipment {r['shipment_id']}:")
        parts.append(f"  Status: {r['status']}, SLA: {r['sla_status']}, Priority: {r['priority']}")
        parts.append(f"  Carrier: {r['carrier_name']}, Service Level: {r['service_level']}")
        parts.append(f"  Route: {r['route_name']} ({r['origin']} → {r['destination']})")
        parts.append(f"  Planned: {r['planned_ship_time']}, Promised: {r['promised_delivery_time']}")
        if r["actual_delivery_time"]:
            parts.append(f"  Actual Delivery: {r['actual_delivery_time']}")

    # Latest ETA
    eta = db.execute(text("""
        SELECT predicted_eta, delay_probability, model_version, prediction_time
        FROM eta_estimates WHERE shipment_id = :sid
        ORDER BY prediction_time DESC LIMIT 1
    """), {"sid": shipment_id}).mappings().fetchone()
    if eta:
        e = dict(eta)
        parts.append(f"  Latest ETA: {e['predicted_eta']} (delay prob: {e['delay_probability']}, model: {e['model_version']})")

    # Recent tracking events
    events = db.execute(text("""
        SELECT event_type, event_time, facility_id, is_duplicate, is_late_arrival
        FROM tracking_events WHERE shipment_id = :sid
        ORDER BY event_time DESC LIMIT 5
    """), {"sid": shipment_id}).mappings().fetchall()
    if events:
        parts.append("  Recent events:")
        for ev in events:
            flags = []
            if ev["is_duplicate"]: flags.append("DUPLICATE")
            if ev["is_late_arrival"]: flags.append("LATE")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            parts.append(f"    {ev['event_type']} at {ev['event_time']}{flag_str}")

    return "\n".join(parts) if parts else f"No data found for shipment {shipment_id}."


def _retrieve_general_context(db: Session, question: str) -> str:
    """Retrieve general operational context based on keywords in the question."""
    q_lower = question.lower()
    parts = []

    if "delay" in q_lower or "sla" in q_lower or "breach" in q_lower:
        row = db.execute(text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN sla_status='BREACHED' THEN 1 ELSE 0 END) AS breached,
                   SUM(CASE WHEN sla_status='AT_RISK' THEN 1 ELSE 0 END) AS at_risk,
                   SUM(CASE WHEN sla_status='ON_TIME' THEN 1 ELSE 0 END) AS on_time
            FROM shipments
        """)).mappings().fetchone()
        if row:
            r = dict(row)
            parts.append(f"SLA Summary: {r['total']} total shipments, {r['on_time']} on-time, "
                        f"{r['at_risk']} at-risk, {r['breached']} breached.")

    if "carrier" in q_lower or "performance" in q_lower:
        rows = db.execute(text("""
            SELECT c.carrier_name, cp.on_time_rate, cp.average_delay_hours, cp.carrier_score
            FROM carrier_performance cp
            JOIN carriers c ON cp.carrier_id = c.carrier_id
            WHERE cp.perf_id LIKE 'CP-%-GOLD'
            ORDER BY cp.carrier_score DESC NULLS LAST LIMIT 5
        """)).mappings().fetchall()
        if rows:
            parts.append("Top carriers:")
            for r in rows:
                parts.append(f"  {r['carrier_name']}: on-time {round(float(r['on_time_rate'] or 0)*100)}%, "
                           f"avg delay {r['average_delay_hours']}h, score {r['carrier_score']}")

    if "facility" in q_lower or "congest" in q_lower:
        rows = db.execute(text("""
            SELECT f.facility_name, f.city, fq.utilization_pct, fq.queue_length, fq.capacity
            FROM facility_queues fq
            JOIN facilities f ON fq.facility_id = f.facility_id
            WHERE fq.timestamp = (SELECT MAX(timestamp) FROM facility_queues fq2 WHERE fq2.facility_id = fq.facility_id)
            ORDER BY fq.utilization_pct DESC LIMIT 5
        """)).mappings().fetchall()
        if rows:
            parts.append("Facility congestion (latest):")
            for r in rows:
                parts.append(f"  {r['facility_name']} ({r['city']}): {round(float(r['utilization_pct']))}% "
                           f"({r['queue_length']}/{r['capacity']})")

    if "weather" in q_lower:
        rows = db.execute(text("""
            SELECT location, weather_type, severity, delay_factor, end_time
            FROM weather_events WHERE end_time >= NOW()
            ORDER BY severity DESC LIMIT 5
        """)).mappings().fetchall()
        if rows:
            parts.append("Active weather events:")
            for r in rows:
                parts.append(f"  {r['weather_type']} at {r['location']} (severity {r['severity']}, "
                           f"delay factor {r['delay_factor']}, ends {r['end_time']})")

    return "\n".join(parts) if parts else ""


def chat(db: Session, message: str) -> dict:
    """Process a user's question and return a grounded AI response.

    Args:
        db: Active SQLAlchemy session for live data retrieval.
        message: The user's natural-language question.

    Returns:
        Dict with 'response' (the AI answer), 'data_sources' (what DB data was used),
        'model' (which LLM model was used), and 'config_required' (if Groq not set up).
    """
    if not _is_configured():
        return _config_message()

    llm = get_llm()
    if llm is None:
        return _config_message()

    # Retrieve live context from PostgreSQL
    context_parts = []
    data_sources = []

    # Check for shipment IDs in the question
    shipment_ids = _SHIPMENT_PATTERN.findall(message)
    for sid in shipment_ids[:3]:  # limit to 3 shipments
        ctx = _retrieve_shipment_context(db, sid)
        context_parts.append(ctx)
        data_sources.append({"type": "shipment", "id": sid})

    # General context based on keywords
    general_ctx = _retrieve_general_context(db, message)
    if general_ctx:
        context_parts.append(general_ctx)
        data_sources.append({"type": "analytics_summary"})

    context = "\n\n".join(context_parts) if context_parts else "No specific operational data retrieved for this question."

    # Call the LLM
    try:
        response_text = llm.chat(
            message=message,
            system_prompt=SYSTEM_PROMPT,
            context=context,
            temperature=0.3,
        )
    except Exception as exc:
        log.error("LLM chat failed: %s", exc)
        return {
            "response": f"Sorry, an error occurred while contacting the LLM: {str(exc)[:200]}",
            "error": str(exc)[:500],
            "model": settings.GROQ_MODEL,
        }

    return {
        "response": response_text,
        "data_sources": data_sources,
        "model": settings.GROQ_MODEL,
        "context_used": bool(context_parts),
    }
