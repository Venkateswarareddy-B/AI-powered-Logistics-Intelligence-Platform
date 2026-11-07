# YottaFlex — API Documentation

Interactive OpenAPI docs available at `http://localhost:8000/docs` when the backend is running.

## Authentication

All endpoints except `/api/health/*` require a JWT bearer token obtained via:

```
POST /api/auth/token
Content-Type: application/x-www-form-urlencoded

username=demo_admin&password=Demo@YottaFlex2026
```

Returns: `{"access_token": "...", "token_type": "bearer", "role": "ADMIN"}`

Use the token: `Authorization: Bearer <token>`

## Endpoint Summary

### Health (no auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App metadata |
| GET | `/api/health` | Liveness |
| GET | `/api/health/database` | DB connectivity |
| GET | `/api/health/ml` | ML model availability |
| GET | `/api/health/llm` | Groq status |
| GET | `/api/health/rag` | ChromaDB + embedding status |
| GET | `/api/health/full` | Comprehensive system health |

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/token` | Login (form-encoded) |
| GET | `/api/auth/me` | Current user info |

### Shipments
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/shipments` | List (filter: status, sla_status, carrier_id; paginate: page, page_size) |
| GET | `/api/shipments/{id}` | Shipment detail |
| GET | `/api/shipments/{id}/tracking` | Tracking events |
| GET | `/api/shipments/{id}/eta` | ETA estimate history |
| GET | `/api/shipments/{id}/delay-risk` | Latest delay probability |
| GET | `/api/shipments/{id}/explanation` | SHAP explanation |
| POST | `/api/eta/predict` | Run ETA prediction (body: `{"shipment_id": "..."}`) |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/summary` | Dashboard KPIs |
| GET | `/api/delays` | Delayed/at-risk shipments |
| GET | `/api/carriers` | Carrier list |
| GET | `/api/carriers/{id}/performance` | Carrier KPIs |
| GET | `/api/facilities` | Facility list |
| GET | `/api/facilities/{id}/queue` | Queue snapshots |

### Alerts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/alerts` | List (filter: status, severity) |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge |
| POST | `/api/alerts/{id}/resolve` | Resolve |

### Notifications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/notifications` | User notifications (filter: unread_only) |
| GET | `/api/notifications/stats` | Unread/read counts |
| POST | `/api/notifications/{id}/read` | Mark read |
| POST | `/api/notifications/read-all` | Mark all read |

### GenAI
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/assistant/chat` | GenAI chat (body: `{"message": "..."}`) |

### RAG
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rag/documents` | List documents |
| POST | `/api/rag/documents` | Create + ingest document |
| POST | `/api/rag/documents/seed-samples` | Seed 7 sample policies |
| POST | `/api/rag/documents/{id}/reingest` | Re-ingest |
| POST | `/api/rag/documents/{id}/deactivate` | Archive |
| POST | `/api/rag/search` | Search (body: `{"query": "...", "n_results": 5}`) |

### Agent
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agent/run` | Run agent (body: `{"request": "..."}`) |

### Routes
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/routes/compare` | What-if analysis (body: `{"shipment_id": "...", "alternative_route_id": "..."}`) |

### Approvals & Audit
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/approvals` | List approvals (filter: status=PENDING) |
| POST | `/api/approvals` | Create approval request |
| POST | `/api/approvals/{id}/decide` | Decide (body: `{"decision": "APPROVED", "decision_reason": "..."}`) |
| GET | `/api/audit` | Audit history (filter: entity_type, action) |

## Error Responses

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 401 | Unauthorized (missing/invalid JWT) |
| 403 | Forbidden (insufficient role) |
| 404 | Not found |
| 422 | Validation error |
| 500 | Server error |
