"""Phase 1/2 setup verification.

Confirms the environment is wired correctly:
- settings load from defaults / .env
- structured logging configures
- the FastAPI app builds and responds on root + health routes
- the database connectivity probe reports its current state (DB may be down)

Run from the project root:
    python -m scripts.verify_setup
"""

from fastapi.testclient import TestClient

from backend.core.config import get_settings
from backend.core.logging import configure_logging, get_logger
from backend.main import app


def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL, debug=settings.DEBUG)
    logger = get_logger("scripts.verify_setup")

    print("================ Configuration ================")
    print(f"APP_NAME      : {settings.APP_NAME}")
    print(f"ENV           : {settings.ENV}")
    print(f"DEBUG         : {settings.DEBUG}")
    print(f"LOG_LEVEL     : {settings.LOG_LEVEL}")
    print(f"CORS_ORIGINS  : {settings.CORS_ORIGINS}")
    print(f"database_url  : {settings.database_url}")
    print(f"groq_enabled  : {settings.GROQ_ENABLED}")
    print(f"rag_enabled   : {settings.RAG_ENABLED}")
    print(f"random_seed   : {settings.RANDOM_SEED}")

    print("\n================ App smoke test ================")
    client = TestClient(app)
    root = client.get("/")
    health = client.get("/api/health")
    db = client.get("/api/health/database")

    print(f"GET /                  -> {root.status_code}  {root.json()}")
    print(f"GET /api/health        -> {health.status_code}  {health.json()}")
    print(f"GET /api/health/database -> {db.status_code}  {db.json()}")

    assert root.status_code == 200, "root route failed"
    assert health.status_code == 200, "health route failed"
    assert health.json()["status"] == "healthy", "health status not healthy"
    assert db.status_code == 200, "database health must return HTTP 200 even if unhealthy"
    assert "status" in db.json(), "database health must report a status"

    logger.info("phase 2 verification passed")
    print("\nPhase 2 verification PASSED.")


if __name__ == "__main__":
    main()
