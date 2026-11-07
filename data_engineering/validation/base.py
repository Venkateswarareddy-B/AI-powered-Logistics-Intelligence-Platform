"""Base types for the validation framework.

ValidationResult is a lightweight dataclass returned by every validator.
BaseValidator is an abstract base class all validators inherit from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ValidationResult:
    """A single validation finding — pass or fail.

    Failed results are persisted as DataQualityIssue rows.
    Passed results are counted for the summary but not persisted.
    """

    passed: bool
    issue_type: str          # matches DataQualityIssue.issue_type enum values
    entity_type: str         # e.g. "Shipment", "TrackingEvent"
    entity_id: str           # PK value of the offending row
    shipment_id: str | None  # for traceability; None when not applicable
    description: str         # human-readable explanation
    severity: str = "MEDIUM" # LOW | MEDIUM | HIGH | CRITICAL
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return not self.passed


class BaseValidator(ABC):
    """Abstract base class for all validators.

    Subclasses implement ``validate(db)`` and return a list of
    ``ValidationResult`` objects. The pipeline calls each validator
    and accumulates results.
    """

    #: Human-readable name shown in logs and the summary report.
    name: str = "unnamed"

    @abstractmethod
    def validate(self, db) -> list[ValidationResult]:
        """Run validation against the live database.

        Args:
            db: An active SQLAlchemy Session.

        Returns:
            List of ValidationResult — one per checked entity.
            Include both passes (passed=True) and failures (passed=False)
            so the summary can report pass rates.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
