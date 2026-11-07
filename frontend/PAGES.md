# YottaFlex Frontend — Page Inventory

Built with: React 18, Vite 5, Tailwind CSS 3, Recharts, Lucide React

## Pages (17 total — all functional)
/ .............. Dashboard (KPIs, donut chart, SLA bar, recent shipments)
/shipments ..... Filterable paginated shipment list
/shipments/:id . Detail with tracking timeline, ETA history, SHAP explanation
/eta ........... Batch ETA prediction for active shipments
/alerts ........ SLA-breached and at-risk shipments
/carriers ...... Carrier KPIs and performance charts
/facilities .... Facility utilization trend charts
/routes ........ Route what-if comparison (ETA/risk/cost)
/ai-assistant .. Groq chat grounded in live DB data
/knowledge ..... Policy docs + website source management + semantic search
/agent ......... Tool-calling AI with transparent execution summary
/reports ....... KPI charts, carrier table, delay report
/notifications . In-app notification center with mark-as-read
/audit ......... Immutable audit trail with action filter
/system ........ Full system health (DB/ML/LLM/RAG)
/users ......... RBAC roles and business actors
/settings ...... Feature status cards and quick actions

## Design System
Colors: Navy #0B1530, Blue #2563EB, Purple #8B5CF6, Green #10B981
Radius: 20px (xl2), Shadows: card/card-hover/soft
Font: Inter (Google Fonts)
