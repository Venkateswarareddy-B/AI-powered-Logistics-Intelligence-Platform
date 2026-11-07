"""Phase 10 API tests."""
from __future__ import annotations
import pytest
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import SessionLocal

# Seed demo user before any test runs (lifespan doesn't fire in TestClient)
def _ensure_seeded():
    try:
        db = SessionLocal()
        from backend.api.auth import seed_demo_user
        seed_demo_user(db)
        db.close()
    except Exception:
        pass

_ensure_seeded()
client = TestClient(app, raise_server_exceptions=True)


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def token(requires_db):
    r = client.post("/api/auth/token",
                    data={"username": "demo_admin", "password": "Demo@YottaFlex2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Health ────────────────────────────────────────────────────────────────────
class TestHealth:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["app"] == "YottaFlex"

    def test_health(self):
        assert client.get("/api/health").status_code == 200

    def test_health_database(self, requires_db):
        r = client.get("/api/health/database")
        assert r.status_code == 200
        assert r.json()["status"] in ("healthy", "unhealthy")

    def test_health_ml(self):
        assert client.get("/api/health/ml").status_code == 200

    def test_health_llm(self):
        assert client.get("/api/health/llm").status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_demo(self, requires_db):
        r = client.post("/api/auth/token",
                        data={"username": "demo_admin", "password": "Demo@YottaFlex2026"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_wrong_password(self, requires_db):
        r = client.post("/api/auth/token",
                        data={"username": "demo_admin", "password": "WRONG"})
        assert r.status_code == 401

    def test_me_endpoint(self, auth, requires_db):
        r = client.get("/api/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["username"] == "demo_admin"

    def test_protected_without_token(self):
        r = client.get("/api/shipments")
        assert r.status_code == 401

    def test_invalid_token(self):
        r = client.get("/api/shipments", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 401


# ── Shipments ─────────────────────────────────────────────────────────────────
class TestShipments:
    def test_list_shipments(self, auth, requires_db):
        r = client.get("/api/shipments", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "items" in data
        assert len(data["items"]) > 0

    def test_list_shipments_pagination(self, auth, requires_db):
        r = client.get("/api/shipments?page=1&page_size=5", headers=auth)
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 5

    def test_list_shipments_filter_status(self, auth, requires_db):
        r = client.get("/api/shipments?status=DELIVERED", headers=auth)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "DELIVERED"

    def test_get_shipment_detail(self, auth, requires_db):
        sids = client.get("/api/shipments?page_size=1", headers=auth).json()["items"]
        if sids:
            sid = sids[0]["shipment_id"]
            r = client.get(f"/api/shipments/{sid}", headers=auth)
            assert r.status_code == 200
            assert r.json()["shipment_id"] == sid

    def test_get_shipment_not_found(self, auth, requires_db):
        r = client.get("/api/shipments/SHP-FAKE-999999", headers=auth)
        assert r.status_code == 404

    def test_get_tracking(self, auth, requires_db):
        sids = client.get("/api/shipments?page_size=1", headers=auth).json()["items"]
        if sids:
            sid = sids[0]["shipment_id"]
            r = client.get(f"/api/shipments/{sid}/tracking", headers=auth)
            assert r.status_code == 200
            assert isinstance(r.json(), list)

    def test_get_eta(self, auth, requires_db):
        sids = client.get("/api/shipments?page_size=1", headers=auth).json()["items"]
        if sids:
            sid = sids[0]["shipment_id"]
            r = client.get(f"/api/shipments/{sid}/eta", headers=auth)
            assert r.status_code == 200

    def test_get_delay_risk(self, auth, requires_db):
        sids = client.get("/api/shipments?page_size=1", headers=auth).json()["items"]
        if sids:
            r = client.get(f"/api/shipments/{sids[0]['shipment_id']}/delay-risk", headers=auth)
            assert r.status_code == 200


# ── Analytics ─────────────────────────────────────────────────────────────────
class TestAnalytics:
    def test_analytics_summary(self, auth, requires_db):
        r = client.get("/api/analytics/summary", headers=auth)
        assert r.status_code == 200
        assert "total" in r.json()

    def test_eta_predict(self, auth, requires_db):
        sids = client.get("/api/shipments?page_size=1", headers=auth).json()["items"]
        if sids:
            r = client.post("/api/eta/predict",
                            json={"shipment_id": sids[0]["shipment_id"]}, headers=auth)
            assert r.status_code == 200

    def test_delays_list(self, auth, requires_db):
        r = client.get("/api/delays", headers=auth)
        assert r.status_code == 200

    def test_carriers_list(self, auth, requires_db):
        r = client.get("/api/carriers", headers=auth)
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_carrier_performance(self, auth, requires_db):
        carriers = client.get("/api/carriers", headers=auth).json()
        if carriers:
            r = client.get(f"/api/carriers/{carriers[0]['carrier_id']}/performance", headers=auth)
            assert r.status_code in (200, 404)

    def test_facilities_list(self, auth, requires_db):
        r = client.get("/api/facilities", headers=auth)
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_facility_queue(self, auth, requires_db):
        facs = client.get("/api/facilities", headers=auth).json()
        if facs:
            r = client.get(f"/api/facilities/{facs[0]['facility_id']}/queue", headers=auth)
            assert r.status_code == 200
