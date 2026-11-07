"""SQLAlchemy ORM models for YottaFlex.

Import order matters for Alembic autogenerate — every model module must be
imported here so ``Base.metadata`` is fully populated when Alembic inspects it.
"""

from backend.models.base import Base  # noqa: F401 — must be first

# Auth / RBAC
from backend.models.auth import Role, User  # noqa: F401

# Reference / config tables
from backend.models.service_level import ServiceLevel  # noqa: F401
from backend.models.carrier import Carrier  # noqa: F401
from backend.models.route import Route  # noqa: F401
from backend.models.facility import Facility, FacilityQueue  # noqa: F401
from backend.models.weather import WeatherEvent  # noqa: F401

# Operational tables
from backend.models.shipment import Shipment, ShipmentLeg  # noqa: F401
from backend.models.tracking import TrackingEvent  # noqa: F401

# Prediction / analytics
from backend.models.eta import ETAEstimate  # noqa: F401
from backend.models.delay import DelayReason, RouteChange  # noqa: F401
from backend.models.performance import CarrierPerformance, FacilityPerformance  # noqa: F401

# Alerting / notifications
from backend.models.alert import Alert  # noqa: F401
from backend.models.notification import Notification, NotificationPreference  # noqa: F401

# Governance / audit
from backend.models.audit import AuditLog  # noqa: F401
from backend.models.agent import AgentDecision  # noqa: F401
from backend.models.approval import HumanApproval  # noqa: F401

# ML / explainability
from backend.models.ml import ModelVersion, PredictionExplanation  # noqa: F401

# Data quality
from backend.models.data_quality import DataQualityIssue  # noqa: F401

# RAG / knowledge base
from backend.models.rag import RAGDocument, RAGIngestionJob  # noqa: F401

# RAG web sources (Phase MASTER)
from backend.models.rag_source import RagWebSource  # noqa: F401

# ETL staging and feature tables (Phase 6)
from backend.models.etl import (  # noqa: F401
    BronzeTrackingEvent, BronzeShipmentSnapshot,
    SilverTrackingEvent, SilverShipment,
    GoldShipmentFeature,
)
