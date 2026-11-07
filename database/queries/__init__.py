"""YottaFlex SQL analytics query library."""
from database.queries.analytics import (
    top_delayed_carriers, top_congested_facilities,
    daily_shipment_volume, sla_compliance,
    avg_delay_by_carrier, avg_delay_by_route,
    latest_event_per_shipment, shipment_event_gaps,
    high_risk_shipments, facility_queue_trends,
    carrier_ranking, route_performance,
)
__all__ = [
    "top_delayed_carriers", "top_congested_facilities",
    "daily_shipment_volume", "sla_compliance",
    "avg_delay_by_carrier", "avg_delay_by_route",
    "latest_event_per_shipment", "shipment_event_gaps",
    "high_risk_shipments", "facility_queue_trends",
    "carrier_ranking", "route_performance",
]
