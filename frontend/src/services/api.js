import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const login = (username, password) =>
  api.post('/api/auth/token', new URLSearchParams({ username, password }),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })

export const getMe = () => api.get('/api/auth/me')
export const getHealth = () => api.get('/api/health')
export const getHealthDB = () => api.get('/api/health/database')
export const getHealthML = () => api.get('/api/health/ml')
export const getHealthLLM = () => api.get('/api/health/llm')
export const getAnalyticsSummary = () => api.get('/api/analytics/summary')
export const getShipments = (params) => api.get('/api/shipments', { params })
export const getShipment = (id) => api.get(`/api/shipments/${id}`)
export const getShipmentTracking = (id) => api.get(`/api/shipments/${id}/tracking`)
export const getShipmentETA = (id) => api.get(`/api/shipments/${id}/eta`)
export const getShipmentDelayRisk = (id) => api.get(`/api/shipments/${id}/delay-risk`)
export const getShipmentExplanation = (id) => api.get(`/api/shipments/${id}/explanation`)
export const predictETA = (shipment_id) => api.post('/api/eta/predict', { shipment_id })
export const getDelays = () => api.get('/api/delays')
export const getCarriers = () => api.get('/api/carriers')
export const getCarrierPerformance = (id) => api.get(`/api/carriers/${id}/performance`)
export const getFacilities = () => api.get('/api/facilities')
export const getFacilityQueue = (id) => api.get(`/api/facilities/${id}/queue`)

// Alerts
export const getAlerts = (params) => api.get('/api/alerts', { params })
export const ackAlert = (id) => api.post(`/api/alerts/${id}/acknowledge`)
export const resolveAlert = (id) => api.post(`/api/alerts/${id}/resolve`)

// Notifications
export const getNotifications = (unreadOnly) => api.get('/api/notifications', { params: unreadOnly ? { unread_only: true } : {} })
export const getNotifStats = () => api.get('/api/notifications/stats')
export const markNotifRead = (id) => api.post(`/api/notifications/${id}/read`)
export const markAllNotifRead = () => api.post('/api/notifications/read-all')

// Routes
export const compareRoutes = (shipment_id, alternative_route_id) => api.post('/api/routes/compare', { shipment_id, alternative_route_id })

// RAG
export const getRagDocuments = () => api.get('/api/rag/documents')
export const createRagDocument = (data) => api.post('/api/rag/documents', data)
export const seedRagSamples = () => api.post('/api/rag/documents/seed-samples')
export const reingestRagDoc = (id) => api.post(`/api/rag/documents/${id}/reingest`)
export const deactivateRagDoc = (id) => api.post(`/api/rag/documents/${id}/deactivate`)
export const searchRag = (query, n_results) => api.post('/api/rag/search', { query, n_results: n_results || 5 })

// Agent
export const runAgent = (request) => api.post('/api/agent/run', { request })

// Approvals & Audit
export const getApprovals = (status) => api.get('/api/approvals', { params: status ? { status } : {} })
export const createApproval = (data) => api.post('/api/approvals', data)
export const decideApproval = (id, decision, reason) => api.post(`/api/approvals/${id}/decide`, { decision, decision_reason: reason })
export const getAuditLogs = (params) => api.get('/api/audit', { params })

// Full health
export const getHealthFull = () => api.get('/api/health/full')
export const getHealthRag = () => api.get('/api/health/rag')

// RAG Web Sources
export const getWebSources = () => api.get('/api/rag/web-sources')
export const addWebSource = (data) => api.post('/api/rag/web-sources', data)
export const ingestWebSource = (id) => api.post(`/api/rag/web-sources/${id}/ingest`)
export const deleteWebSource = (id) => api.delete(`/api/rag/web-sources/${id}`)

export default api
