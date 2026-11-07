# Agent Tools Reference

| Tool | Input | Description |
|------|-------|-------------|
| get_shipment | shipment_id | Full shipment details from live DB |
| get_tracking_events | shipment_id | Tracking event history |
| get_eta | shipment_id | Latest ETA prediction |
| get_delay_risk | shipment_id | ML-based delay probability |
| get_weather | location? | Active weather disruptions |
| get_facility_queue | facility_id | Queue utilization snapshots |
| get_carrier_performance | carrier_id | Carrier KPI metrics |
| search_policy | query | RAG knowledge base search |
| get_sla_status | shipment_id | SLA compliance status |
| compare_routes | shipment_id | What-if route comparison |
| generate_report | type | Operational summary/carrier report |
| search_shipments | status?, sla? | Filter shipments by criteria |
| get_high_risk_shipments | limit | At-risk and breached shipments |
| get_sla_statistics | — | Platform-wide SLA compliance |
| search_knowledge_base | query | Semantic knowledge search |
| generate_logistics_summary | — | Comprehensive ops overview |
