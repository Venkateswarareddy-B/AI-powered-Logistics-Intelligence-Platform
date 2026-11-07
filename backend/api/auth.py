"""Auth endpoints — login, demo user seeding."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.security import verify_password, create_access_token, hash_password, get_current_user
from backend.core.config import get_settings
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def seed_demo_user(db: Session) -> None:
    """Ensure roles and demo user exist. Safe to call multiple times."""
    roles = [
        ("ADMIN","Administrator"),("PLANNER","Planner"),
        ("ANALYST","Analyst"),("OPERATOR","Operator"),("MANAGER","Manager"),
    ]
    now = datetime.now(timezone.utc)
    for rid, rname in roles:
        db.execute(text("""
            INSERT INTO roles (role_id,role_name,is_active,created_at,updated_at)
            VALUES (:rid,:rname,TRUE,:now,:now) ON CONFLICT DO NOTHING
        """), {"rid": rid, "rname": rname, "now": now})

    if settings.DEMO_USER_ENABLED:
        db.execute(text("""
            INSERT INTO users (user_id,username,full_name,hashed_password,role_id,
                               is_active,is_demo,created_at,updated_at)
            VALUES (:uid,:uname,:fname,:hp,:role,TRUE,TRUE,:now,:now)
            ON CONFLICT (username) DO NOTHING
        """), {
            "uid": f"USR-DEMO-{uuid.uuid4().hex[:8].upper()}",
            "uname": settings.DEMO_USERNAME,
            "fname": settings.DEMO_USER_FULL_NAME,
            "hp": hash_password(settings.DEMO_PASSWORD),
            "role": settings.DEMO_USER_ROLE,
            "now": now,
        })
    db.commit()


@router.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    row = db.execute(text(
        "SELECT user_id,username,hashed_password,role_id,is_active FROM users WHERE username=:u"
    ), {"u": form.username}).mappings().fetchone()
    if not row or not row["is_active"] or not verify_password(form.password, row["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials")
    token = create_access_token({"sub": row["username"], "role": row["role_id"]})
    db.execute(text("UPDATE users SET last_login_at=:now WHERE user_id=:uid"),
               {"now": datetime.now(timezone.utc), "uid": row["user_id"]})
    db.commit()
    return {"access_token": token, "token_type": "bearer",
            "role": row["role_id"], "username": row["username"]}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return current_user
