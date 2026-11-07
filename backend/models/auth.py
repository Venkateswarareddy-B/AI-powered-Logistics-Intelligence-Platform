"""Auth models: Role and User.

Password hashes are stored, never plaintext passwords.
Roles are reference rows (ADMIN, PLANNER, ANALYST, OPERATOR, MANAGER).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    """Reference table for application roles."""

    __tablename__ = "roles"

    role_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list[User]] = relationship("User", back_populates="role")

    __table_args__ = (
        CheckConstraint(
            "role_id IN ('ADMIN','PLANNER','ANALYST','OPERATOR','MANAGER')",
            name="ck_roles_role_id",
        ),
    )

    def __repr__(self) -> str:
        return f"<Role {self.role_id}>"


class User(Base, TimestampMixin):
    """Application users. Passwords stored as bcrypt hashes."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.role_id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship("Role", back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.username} role={self.role_id}>"
