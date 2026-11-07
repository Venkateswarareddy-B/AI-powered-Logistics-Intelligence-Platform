"""Phase 23 Monitoring tests."""
from __future__ import annotations
import pytest
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.main import app
from backend.core.database import SessionLocal
from backend.services.monitoring import (
    get_database_status, get_ml_status, get_llm_status,
    get_rag_status, get_last_successful_ingestion,
    get_last_successful_prediction, get_recent_errors, get_system_health,
)

client = TestClient(app)


class TestIndividualChecks:
    def test_database_status(self, requires_db):
        s = get_database_status()
        assert s["status"] in ("healthy", "unhealthy")

    def test_ml_status(self):
        s = get_ml_status()
        assert s["status"] in ("available", "partial", "no_models_trained")
        assert "eta_models" in s
        assert "delay_models" in s

    def test_llm_status(self):
        s = get_llm_status()
        assert s["status"] in ("configured", "not_configured")
        # Must not expose API key
        assert "api_key" not in str(s).lower()

    def test_rag_status(self, requires_db):
        db = SessionLocal()
        try:
            s = get_rag_status(db)
            assert s["status"] in ("available", "initialized_empty", "no_embeddings", "error", "unavailable")
        finally:
            db.close()

    def test_last_ingestion(self, requires_db):
        db = SessionLocal()
        try:
            r = get_last_successful_ingestion(db)
            assert r["status"] in ("available", "never_run", "error")
        finally:
            db.close()

    def test_last_prediction(self, requires_db):
        db = SessionLocal()
        try:
            r = get_last_successful_prediction(db)
            assert r["status"] in ("available", "never_run", "error")
        finally:
            db.close()

    def test_recent_errors(self, requires_db):
        db = SessionLocal()
        try:
            errors = get_recent_errors(db, limit=5)
            assert isinstance(errors, list)
            assert len(errors) <= 5
        finally:
            db.close()


class TestSystemHealth:
    def test_returns_comprehensive_dict(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            assert "overall_status" in health
            assert "app" in health
            assert "checks" in health
            assert "operational" in health
            assert "configuration" in health
        finally:
            db.close()

    def test_overall_status_valid(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            assert health["overall_status"] in ("healthy", "degraded")
        finally:
            db.close()

    def test_checks_contain_all_subsystems(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            checks = health["checks"]
            assert "backend" in checks
            assert "database" in checks
            assert "ml" in checks
            assert "llm" in checks
            assert "rag" in checks
        finally:
            db.close()

    def test_operational_has_ingestion_and_prediction(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            ops = health["operational"]
            assert "last_successful_ingestion" in ops
            assert "last_successful_prediction" in ops
            assert "recent_errors" in ops
            assert "error_count" in ops
        finally:
            db.close()

    def test_no_secrets_exposed(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            health_str = str(health).lower()
            assert "password" not in health_str
            assert "secret" not in health_str
            assert "api_key" not in health_str
            assert "connection string" not in health_str
        finally:
            db.close()

    def test_configuration_flags_present(self, requires_db):
        db = SessionLocal()
        try:
            health = get_system_health(db)
            cfg = health["configuration"]
            assert "groq_enabled" in cfg
            assert "rag_enabled" in cfg
            assert "debug" in cfg
        finally:
            db.close()


class TestHealthAPI:
    def test_health_full_endpoint(self):
        r = client.get("/api/health/full")
        assert r.status_code == 200
        data = r.json()
        assert "overall_status" in data
        assert "checks" in data

    def test_health_rag_endpoint(self):
        r = client.get("/api/health/rag")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_health_full_no_secrets(self):
        r = client.get("/api/health/full")
        data_str = str(r.json()).lower()
        assert "password" not in data_str
        assert "api_key" not in data_str

    def test_health_full_has_timestamp(self):
        r = client.get("/api/health/full")
        assert "timestamp" in r.json()
