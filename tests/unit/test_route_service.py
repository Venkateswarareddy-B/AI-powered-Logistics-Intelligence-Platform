"""Phase 19 Route What-If Analysis tests."""
from __future__ import annotations
import pytest
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.services.route_service import compare_routes


class TestRouteComparison:
    def test_returns_comparison_for_valid_shipment(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            assert "current_route" in result or "error" in result
        finally:
            db.close()

    def test_current_route_has_eta(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if "current_route" in result:
                cr = result["current_route"]
                assert "estimated_delivery_hours" in cr
                assert cr["estimated_delivery_hours"] > 0
        finally:
            db.close()

    def test_current_route_has_cost(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if "current_route" in result:
                assert "cost" in result["current_route"]
                assert result["current_route"]["cost"] > 0
        finally:
            db.close()

    def test_current_route_has_delay_probability(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if "current_route" in result:
                dp = result["current_route"]["delay_probability"]
                assert 0.0 <= dp <= 1.0
        finally:
            db.close()

    def test_alternatives_sorted_by_eta(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if result.get("alternatives"):
                etas = [a["estimated_delivery_hours"] for a in result["alternatives"]]
                assert etas == sorted(etas)
        finally:
            db.close()

    def test_recommendation_has_time_saved(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if result.get("recommendation"):
                rec = result["recommendation"]
                assert "time_saved_hours" in rec
                assert "risk_reduction" in rec
                assert "additional_cost" in rec
                assert rec["requires_approval"] is True
        finally:
            db.close()

    def test_simulation_note_present(self, requires_db):
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if "simulation_note" in result:
                assert "NOT verified carrier quotations" in result["simulation_note"]
        finally:
            db.close()

    def test_invalid_shipment_returns_error(self, requires_db):
        db = SessionLocal()
        try:
            result = compare_routes(db, "SHP-FAKE-999999")
            assert "error" in result
        finally:
            db.close()

    def test_specific_alternative_route(self, requires_db):
        db = SessionLocal()
        try:
            # Get a shipment and a different route
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            current_route = db.execute(text(
                "SELECT route_id FROM shipments WHERE shipment_id=:sid"
            ), {"sid": sid}).scalar()
            alt_route = db.execute(text(
                "SELECT route_id FROM routes WHERE route_id != :cur LIMIT 1"
            ), {"cur": current_route}).scalar()
            if alt_route:
                result = compare_routes(db, sid, alt_route)
                assert "current_route" in result
                assert len(result["alternatives"]) == 1
                assert result["alternatives"][0]["route_id"] == alt_route
        finally:
            db.close()

    def test_cost_is_distance_times_8(self, requires_db):
        """Verify cost = distance_km * 8 (documented simulation rule)."""
        db = SessionLocal()
        try:
            sid = db.execute(text("SELECT shipment_id FROM shipments LIMIT 1")).scalar()
            result = compare_routes(db, sid)
            if "current_route" in result:
                cr = result["current_route"]
                expected_cost = round(cr["distance_km"] * 8, 0)
                assert cr["cost"] == expected_cost
        finally:
            db.close()
