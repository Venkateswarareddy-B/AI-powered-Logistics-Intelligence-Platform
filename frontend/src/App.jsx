import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'

import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Shipments from './pages/Shipments'
import ShipmentDetail from './pages/ShipmentDetail'
import ETAPrediction from './pages/ETAPrediction'
import DelayAlerts from './pages/DelayAlerts'
import Carriers from './pages/Carriers'
import Facilities from './pages/Facilities'
import RouteOptimization from './pages/RouteOptimization'
import AIAssistant from './pages/AIAssistant'
import KnowledgeBase from './pages/KnowledgeBase'
import Agent from './pages/Agent'
import Reports from './pages/Reports'
import Notifications from './pages/Notifications'
import AuditHistory from './pages/AuditHistory'
import SystemHealth from './pages/SystemHealth'
import UserManagement from './pages/UserManagement'
import Settings from './pages/Settings'

function Protected({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={
        <Protected>
          <Layout>
            <Routes>
              <Route index element={<Dashboard />} />
              <Route path="shipments" element={<Shipments />} />
              <Route path="shipments/:id" element={<ShipmentDetail />} />
              <Route path="eta" element={<ETAPrediction />} />
              <Route path="alerts" element={<DelayAlerts />} />
              <Route path="carriers" element={<Carriers />} />
              <Route path="facilities" element={<Facilities />} />
              <Route path="routes" element={<RouteOptimization />} />
              <Route path="ai-assistant" element={<AIAssistant />} />
              <Route path="knowledge" element={<KnowledgeBase />} />
              <Route path="agent" element={<Agent />} />
              <Route path="reports" element={<Reports />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="audit" element={<AuditHistory />} />
              <Route path="system" element={<SystemHealth />} />
              <Route path="users" element={<UserManagement />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </Protected>
      } />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
