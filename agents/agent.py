"""YottaFlex Logistics Agent.

A tool-calling agent that uses live DB tools to answer operational questions.
The agent does NOT guess — it calls tools to get verified data, then generates
a recommendation using the Groq LLM (if configured) or a rule-based summary.

Key design:
  - The agent decides which tools to call based on keywords in the request.
  - Tool execution summary is transparent (no hidden chain-of-thought).
  - Errors are handled gracefully per tool.
  - Recommendations that require operational action include approval requirement.
  - An AgentDecision record is persisted for audit.

Usage:
  from agents.agent import run_agent
  result = run_agent(db, "Find all high-risk shipments and recommend actions")
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from agents.tools.logistics_tools import TOOL_REGISTRY

settings = get_settings()
log = logging.getLogger("agents.agent")


def _decide_tools(request: str) -> list[str]:
    """Heuristic tool selection based on keywords in the request."""
    r = request.lower()
    tools = []

    # Shipment ID detection — always get full details
    shipment_ids = re.findall(r"SHP-\d{4}-\d{6}", request, re.IGNORECASE)
    if shipment_ids:
        tools.extend(["get_shipment", "get_tracking_events", "get_eta",
                       "get_delay_risk", "get_sla_status"])

    # High-risk / delay / breach
    if any(w in r for w in ["high-risk", "high risk", "at risk", "delay", "breach", "late", "delayed"]):
        tools.append("get_high_risk_shipments")

    # Carrier
    if any(w in r for w in ["carrier", "performance", "worst", "best carrier", "on-time"]):
        tools.append("get_carrier_performance")

    # Weather
    if any(w in r for w in ["weather", "rain", "storm", "fog", "flood"]):
        tools.append("get_weather")

    # Facility
    if any(w in r for w in ["facility", "congest", "queue", "warehouse"]):
        tools.append("get_facility_queue")

    # Route
    if any(w in r for w in ["route", "alternative", "reroute", "what-if"]):
        tools.append("compare_routes")

    # Policy / knowledge base
    if any(w in r for w in ["policy", "sop", "procedure", "rule", "escalat", "how to", "what is", "knowledge"]):
        tools.extend(["search_policy", "search_knowledge_base"])

    # SLA statistics
    if any(w in r for w in ["sla", "compliance", "on time", "on-time", "breach rate"]):
        tools.append("get_sla_statistics")

    # Count / how many
    if any(w in r for w in ["how many", "count", "number of", "in transit", "status"]):
        tools.append("search_shipments")

    # Report / summary
    if any(w in r for w in ["report", "summary", "summarize", "today", "situation", "overview", "operations"]):
        tools.append("generate_logistics_summary")

    # Default: if no tools selected, get a summary
    if not tools:
        tools.append("generate_logistics_summary")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _execute_tools(
    db: Session,
    request: str,
    tool_names: list[str],
) -> list[dict]:
    """Execute the selected tools and collect results."""
    results = []
    shipment_ids = re.findall(r"SHP-\d{4}-\d{6}", request, re.IGNORECASE)

    for name in tool_names:
        func = TOOL_REGISTRY.get(name)
        if not func:
            results.append({"tool": name, "error": f"Unknown tool: {name}"})
            continue

        try:
            if name in ("get_shipment", "get_tracking_events", "get_eta",
                        "get_delay_risk", "get_sla_status"):
                if shipment_ids:
                    output = func(db, shipment_ids[0])
                else:
                    output = {"error": "No shipment ID found in request"}
            elif name == "get_weather":
                output = func(db)
            elif name == "get_facility_queue":
                fac_match = re.findall(r"FAC-\d{3}", request, re.IGNORECASE)
                if fac_match:
                    output = func(db, fac_match[0])
                else:
                    fid = db.execute(text("SELECT facility_id FROM facilities LIMIT 1")).scalar()
                    output = func(db, fid) if fid else {"error": "No facilities found"}
            elif name == "get_carrier_performance":
                crr_match = re.findall(r"CRR-\d{3}", request, re.IGNORECASE)
                if crr_match:
                    output = func(db, crr_match[0])
                else:
                    cid = db.execute(text("SELECT carrier_id FROM carriers LIMIT 1")).scalar()
                    output = func(db, cid) if cid else {"error": "No carriers found"}
            elif name in ("search_policy", "search_knowledge_base"):
                output = func(db, request, n_results=3)
            elif name == "compare_routes":
                output = func(db, shipment_ids[0] if shipment_ids else "SHP-2026-000001")
            elif name == "generate_report":
                output = func(db, "carriers" if "carrier" in request.lower() else "summary")
            elif name == "search_shipments":
                # Detect status filter from the question
                status_map = {"in transit": "IN_TRANSIT", "delivered": "DELIVERED",
                              "cancelled": "CANCELLED", "exception": "EXCEPTION"}
                detected = next((v for k, v in status_map.items() if k in request.lower()), None)
                output = func(db, status=detected, limit=20)
            elif name == "get_high_risk_shipments":
                output = func(db, limit=20)
            elif name == "get_sla_statistics":
                output = func(db)
            elif name == "generate_logistics_summary":
                output = func(db)
            else:
                output = {"error": f"No handler for tool {name}"}

            results.append({"tool": name, "output": output})
        except Exception as e:
            results.append({"tool": name, "error": str(e)})

    return results


def _build_recommendation(request: str, tool_results: list[dict]) -> str:
    """Build a recommendation from tool results.

    Uses Groq LLM if configured; otherwise returns a rule-based summary.
    """
    # Summarize findings from tool results
    findings = []
    for tr in tool_results:
        tool_name = tr["tool"]
        output = tr.get("output") or tr.get("error")
        if isinstance(output, dict) and "error" not in output:
            findings.append(f"[{tool_name}] {json.dumps(output, default=str)[:300]}")
        elif isinstance(output, list) and output:
            findings.append(f"[{tool_name}] {len(output)} results: {json.dumps(output[:2], default=str)[:300]}")
        elif isinstance(output, dict) and "error" in output:
            findings.append(f"[{tool_name}] ERROR: {output['error']}")

    findings_text = "\n".join(findings) if findings else "No data retrieved."

    # Try LLM
    if settings.GROQ_ENABLED and settings.GROQ_API_KEY:
        try:
            from genai.llm.provider import get_llm
            llm = get_llm()
            if llm:
                system = (
                    "You are YottaFlex, a logistics operations agent. "
                    "Based on the tool execution results below, provide a concise recommendation. "
                    "Separate verified facts from recommendations. "
                    "If an operational action is recommended, note that it requires human approval. "
                    "Be transparent about data limitations."
                )
                return llm.chat(
                    message=request,
                    system_prompt=system,
                    context=f"Tool execution results:\n{findings_text}",
                    temperature=0.2,
                )
        except Exception as exc:
            log.warning("LLM recommendation failed, using rule-based: %s", exc)

    # Rule-based fallback
    parts = [
        "## YottaFlex Agent Recommendation (Rule-Based)\n",
        f"**Request:** {request}\n",
        f"**Tools used:** {', '.join(tr['tool'] for tr in tool_results)}\n",
        f"**Findings:**\n{findings_text}\n",
    ]
    parts.append("\n**Note:** This is a rule-based summary. Configure GROQ_API_KEY for AI-generated recommendations.")
    parts.append("\n**Approval required:** Any operational action (route change, carrier swap) requires human approval via the Human Approval workflow.")
    return "\n".join(parts)


def _persist_decision(
    db: Session,
    request: str,
    tool_results: list[dict],
    recommendation: str,
    user_id: str | None = None,
) -> str:
    """Persist an AgentDecision record for audit."""
    import uuid
    decision_id = f"AGD-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)

    tools_used = json.dumps([
        {"tool": tr["tool"], "has_error": "error" in (tr.get("output") or tr.get("error") or {})}
        for tr in tool_results
    ], default=str)

    db.execute(text("""
        INSERT INTO agent_decisions (
            agent_decision_id, user_id, request_text, tools_used,
            recommendation, approval_status, model_version, created_at, updated_at
        ) VALUES (
            :aid, :uid, :req, :tools,
            :rec, 'PENDING_REVIEW', :mv, :now, :now
        ) ON CONFLICT (agent_decision_id) DO NOTHING
    """), {
        "aid": decision_id, "uid": user_id,
        "req": request[:2000], "tools": tools_used,
        "rec": recommendation[:5000],
        "mv": settings.GROQ_MODEL if settings.GROQ_ENABLED else "rule_based",
        "now": now,
    })
    db.commit()
    return decision_id


def run_agent(
    db: Session,
    request: str,
    user_id: str | None = None,
) -> dict:
    """Run the logistics agent for a user request.

    Returns a transparent execution summary with:
      - tools_used
      - data_retrieved
      - findings
      - recommendation
      - supporting_policy_sources (if policy search was used)
      - confidence_note
      - approval_requirement
      - agent_decision_id (for audit)
    """
    # 1. Decide which tools to call
    tool_names = _decide_tools(request)
    log.info("agent tools selected: %s", tool_names)

    # 2. Execute tools
    tool_results = _execute_tools(db, request, tool_names)

    # 3. Extract policy sources if search_policy was used
    policy_sources = []
    for tr in tool_results:
        if tr["tool"] == "search_policy":
            output = tr.get("output", [])
            if isinstance(output, list):
                for p in output:
                    if isinstance(p, dict) and "document_name" in p:
                        policy_sources.append({
                            "document": p["document_name"],
                            "category": p.get("category"),
                            "excerpt": p.get("source_excerpt", "")[:200],
                        })

    # 4. Build recommendation
    recommendation = _build_recommendation(request, tool_results)

    # 5. Determine confidence
    has_errors = any("error" in (tr.get("output") or tr.get("error") or {}) for tr in tool_results)
    confidence = "high" if not has_errors and tool_results else "medium" if tool_results else "low"

    # 6. Persist decision
    decision_id = _persist_decision(db, request, tool_results, recommendation, user_id)

    # 7. Build transparent summary
    return {
        "agent_decision_id": decision_id,
        "request": request,
        "tools_used": [{"tool": tr["tool"], "success": "error" not in (tr.get("output") or tr.get("error") or {})}
                       for tr in tool_results],
        "data_retrieved": [
            {"tool": tr["tool"],
             "summary": json.dumps(tr.get("output") or tr.get("error"), default=str)[:200]}
            for tr in tool_results
        ],
        "findings": recommendation,
        "recommendation": recommendation,
        "supporting_policy_sources": policy_sources,
        "confidence": confidence,
        "confidence_note": f"Confidence is {confidence} based on tool execution results. "
                           "Data is from live PostgreSQL — not LLM-generated.",
        "approval_required": any(w in request.lower() for w in
                                 ["route change", "reroute", "approve", "execute", "swap"]),
        "model_version": settings.GROQ_MODEL if settings.GROQ_ENABLED else "rule_based_agent_v1",
    }
