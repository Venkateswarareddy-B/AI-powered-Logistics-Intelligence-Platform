# YottaFlex — Agentic AI

## Architecture

```
User Request → Tool Selection (keyword-based)
             → Tool Execution (11 tools, live DB queries)
             → Recommendation (Groq LLM if configured, rule-based fallback)
             → AgentDecision persisted (PENDING_REVIEW)
             → Transparent execution summary
```

## 11 Tools

| Tool | Input | Output | Data Source |
|------|-------|--------|-------------|
| `get_shipment` | shipment_id | Shipment details | PostgreSQL |
| `get_tracking_events` | shipment_id | Event list | PostgreSQL |
| `get_eta` | shipment_id | Latest ETA estimate | PostgreSQL |
| `get_delay_risk` | shipment_id | Delay probability | ML model |
| `get_weather` | location (optional) | Active weather events | PostgreSQL |
| `get_facility_queue` | facility_id | Queue snapshots | PostgreSQL |
| `get_carrier_performance` | carrier_id | KPI metrics | PostgreSQL |
| `search_policy` | query text | RAG citations | ChromaDB |
| `get_sla_status` | shipment_id | SLA status | PostgreSQL |
| `compare_routes` | shipment_id + alt route | What-if comparison | PostgreSQL |
| `generate_report` | report_type | Summary or carrier report | PostgreSQL |

## Transparency

The agent returns:
- `tools_used`: Which tools were called (name + success/failure)
- `data_retrieved`: Summary of data from each tool
- `findings`: The recommendation text
- `supporting_policy_sources`: RAG citations if policy search was used
- `confidence`: high/medium/low based on tool execution success
- `confidence_note`: "Data is from live PostgreSQL — not LLM-generated"
- `approval_required`: True if request mentions operational actions

**Does NOT expose hidden chain-of-thought.**

## Error Handling

- Missing shipment → `{"error": "Shipment not found"}` (graceful, no crash)
- Tool failure → Error captured in results, other tools continue
- LLM unavailable → Rule-based recommendation fallback

## Persistence

Every agent run creates an `agent_decisions` row:
- `request_text`: The user's request
- `tools_used`: JSON array of tool execution results
- `recommendation`: The generated recommendation
- `approval_status`: `PENDING_REVIEW` (requires human review)

## API

```powershell
POST /api/agent/run
{"request": "Find all high-risk shipments and recommend actions"}
```
