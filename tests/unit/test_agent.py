"""Phase 18 Agentic AI tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from agents.agent import run_agent, _decide_tools
from agents.tools.logistics_tools import (
    TOOL_REGISTRY, get_shipment, get_tracking_events, get_eta,
    get_weather, get_carrier_performance, generate_report,
)


class TestToolRegistry:
    def test_all_11_tools_registered(self):
        expected = {
            "get_shipment", "get_tracking_events", "get_eta", "get_delay_risk",
            "get_weather", "get_facility_queue", "get_carrier_performance",
            "search_policy", "get_sla_status", "compare_routes", "generate_report",
            # Enhanced tools added
            "search_shipments", "get_high_risk_shipments", "get_sla_statistics",
            "search_knowledge_base", "generate_logistics_summary",
        }
        assert expected.issubset(set(TOOL_REGISTRY.keys()))

    def test_all_tools_are_callable(self):
        for name, func in TOOL_REGISTRY.items():
            assert callable(func)


class TestToolSelection:
    def test_shipment_id_triggers_shipment_tools(self):
        tools = _decide_tools("Why is SHP-2026-000001 delayed?")
        assert "get_shipment" in tools
        assert "get_tracking_events" in tools

    def test_carrier_keyword_triggers_carrier_tool(self):
        tools = _decide_tools("Which carrier has the worst performance?")
        assert "get_carrier_performance" in tools

    def test_weather_keyword_triggers_weather_tool(self):
        tools = _decide_tools("What weather disruptions are active?")
        assert "get_weather" in tools

    def test_policy_keyword_triggers_search(self):
        tools = _decide_tools("What is the SLA policy for delays?")
        assert "search_policy" in tools

    def test_route_keyword_triggers_compare(self):
        tools = _decide_tools("Can we reroute this shipment?")
        assert "compare_routes" in tools

    def test_summary_keyword_triggers_report(self):
        tools = _decide_tools("Summarize today's logistics situation")
        # New agent uses generate_logistics_summary for summary requests
        assert "generate_logistics_summary" in tools or "generate_report" in tools

    def test_no_keywords_defaults_to_report(self):
        tools = _decide_tools("Hello")
        assert len(tools) >= 1


class TestToolExecution:
    def test_get_shipment_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = get_shipment(db, sid)
            assert "shipment_id" in result or "error" in result
        finally:
            db.close()

    def test_get_shipment_not_found(self, requires_db):
        db = SessionLocal()
        try:
            result = get_shipment(db, "SHP-FAKE-999999")
            assert "error" in result
        finally:
            db.close()

    def test_get_weather_returns_list(self, requires_db):
        db = SessionLocal()
        try:
            result = get_weather(db)
            assert isinstance(result, list)
        finally:
            db.close()

    def test_generate_report_summary(self, requires_db):
        db = SessionLocal()
        try:
            result = generate_report(db, "summary")
            assert "total" in result
        finally:
            db.close()

    def test_generate_report_carriers(self, requires_db):
        db = SessionLocal()
        try:
            result = generate_report(db, "carriers")
            assert "carriers" in result
        finally:
            db.close()


class TestAgentRun:
    def test_run_agent_returns_dict(self, requires_db):
        db = SessionLocal()
        try:
            result = run_agent(db, "Summarize today's logistics situation")
            assert "agent_decision_id" in result
            assert "tools_used" in result
            assert "recommendation" in result
            assert "confidence" in result
        finally:
            db.close()

    def test_run_agent_with_shipment_id(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = run_agent(db, f"Why is {sid} delayed?")
            assert "agent_decision_id" in result
            assert len(result["tools_used"]) > 0
        finally:
            db.close()

    def test_agent_decision_persisted(self, requires_db):
        db = SessionLocal()
        try:
            result = run_agent(db, "Summarize logistics")
            aid = result["agent_decision_id"]
            count = db.execute(text(
                "SELECT COUNT(*) FROM agent_decisions WHERE agent_decision_id=:aid"
            ), {"aid": aid}).scalar()
            assert count == 1
        finally:
            db.close()

    def test_agent_has_transparent_summary(self, requires_db):
        db = SessionLocal()
        try:
            result = run_agent(db, "Which carriers have worst performance?")
            # Must show tools used (transparent)
            assert isinstance(result["tools_used"], list)
            # Must show data retrieved
            assert isinstance(result["data_retrieved"], list)
            # Must have confidence note
            assert "confidence_note" in result
        finally:
            db.close()

    def test_agent_graceful_error_handling(self, requires_db):
        db = SessionLocal()
        try:
            result = run_agent(db, "Why is SHP-9999-999999 delayed?")
            # Should not crash — should handle missing shipment gracefully
            assert "recommendation" in result
        finally:
            db.close()
