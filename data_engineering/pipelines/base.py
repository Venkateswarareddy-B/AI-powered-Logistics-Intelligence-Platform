"""Base types for the ETL pipeline jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class JobResult:
    """Result returned by every ETLJob.run()."""

    job_name: str
    stage: str                    # BRONZE | SILVER | GOLD
    started_at: datetime
    finished_at: datetime | None = None
    rows_read: int = 0
    rows_written: int = 0
    rows_skipped: int = 0         # duplicates / anomalies preserved but skipped
    errors: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def finish(self) -> "JobResult":
        self.finished_at = datetime.now(timezone.utc)
        return self


class ETLJob(ABC):
    """Abstract base class for all ETL jobs."""

    name: str = "unnamed_job"
    stage: str = "UNKNOWN"        # BRONZE | SILVER | GOLD

    def run(self, db) -> JobResult:
        started = datetime.now(timezone.utc)
        result = JobResult(job_name=self.name, stage=self.stage, started_at=started)
        try:
            self._execute(db, result)
        except Exception as exc:
            result.errors.append(str(exc))
            import logging
            logging.getLogger("data_engineering.pipelines.base").error(
                "job=%s error=%s", self.name, exc, exc_info=True
            )
        finally:
            result.finish()
        return result

    @abstractmethod
    def _execute(self, db, result: JobResult) -> None:
        """Implement the ETL logic. Mutate result in place."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} stage={self.stage}>"
