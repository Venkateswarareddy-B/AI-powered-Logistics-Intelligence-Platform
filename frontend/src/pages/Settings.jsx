import React, { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import { getHealthFull, getMe } from '../services/api'
import { Settings as SettingsIcon, Bell, Bot, Database, Shield, Zap, CheckCircle, XCircle } from 'lucide-react'

export default function Settings() {
  const [health, setHealth] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([getHealthFull(), getMe()])
      .then(([h, u]) => {
        if (h.status === 'fulfilled') setHealth(h.value.data)
        if (u.status === 'fulfilled') setUser(u.value.data)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6">Loading...</div>

  const checks = health?.checks || {}

  return (
    <div>
      <PageHeader title="Settings" subtitle="Platform configuration and feature status" />

      {/* Feature Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {/* GenAI Status */}
        <div className={`bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all ${checks.llm?.status === 'configured' ? 'border-green-200' : 'border-orange-200'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${checks.llm?.status === 'configured' ? 'bg-green-50 text-green-600' : 'bg-orange-50 text-orange-500'}`}>
              <Bot size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">GenAI Assistant</span>
          </div>
          {checks.llm?.status === 'configured' ? (
            <div className="text-sm text-green-600 flex items-center gap-1"><CheckCircle size={14} /> Active — {checks.llm.model}</div>
          ) : (
            <div>
              <div className="text-sm text-orange-600 flex items-center gap-1 mb-1"><XCircle size={14} /> Not configured</div>
              <div className="text-xs text-gray-400">Get a free key at console.groq.com/keys, set GROQ_API_KEY and GROQ_ENABLED=true in .env</div>
            </div>
          )}
        </div>

        {/* RAG Status */}
        <div className={`bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all ${checks.rag?.status === 'available' ? 'border-green-200' : 'border-orange-200'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${checks.rag?.status === 'available' ? 'bg-green-50 text-green-600' : 'bg-orange-50 text-orange-500'}`}>
              <Database size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">RAG Knowledge Base</span>
          </div>
          {checks.rag?.status === 'available' ? (
            <div className="text-sm text-green-600 flex items-center gap-1"><CheckCircle size={14} /> {checks.rag.vector_chunks} chunks, {checks.rag.active_documents} docs</div>
          ) : (
            <div className="text-sm text-orange-600 flex items-center gap-1"><XCircle size={14} /> {checks.rag?.status || 'Not initialized'}</div>
          )}
        </div>

        {/* Database Status */}
        <div className={`bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all ${checks.database?.status === 'healthy' ? 'border-green-200' : 'border-red-200'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${checks.database?.status === 'healthy' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
              <Shield size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">Database</span>
          </div>
          <div className={`text-sm flex items-center gap-1 ${checks.database?.status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
            {checks.database?.status === 'healthy' ? <CheckCircle size={14} /> : <XCircle size={14} />}
            {checks.database?.status === 'healthy' ? `Connected (${checks.database.latency_ms}ms)` : 'Disconnected'}
          </div>
          <div className="text-xs text-gray-400 mt-1">{checks.database?.database || '—'}</div>
        </div>

        {/* ML Models */}
        <div className={`bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all ${checks.ml?.status === 'available' ? 'border-green-200' : 'border-orange-200'}`}>
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${checks.ml?.status === 'available' ? 'bg-green-50 text-green-600' : 'bg-orange-50 text-orange-500'}`}>
              <Zap size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">ML Models</span>
          </div>
          <div className="text-sm text-gray-600">ETA: {checks.ml?.eta_models || 0} · Delay: {checks.ml?.delay_models || 0}</div>
        </div>

        {/* Notifications */}
        <div className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-blue-50 text-blue-600">
              <Bell size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">Notifications</span>
          </div>
          <div className="text-sm text-green-600 flex items-center gap-1"><CheckCircle size={14} /> In-app active</div>
          <div className="text-xs text-gray-400 mt-1">Email/SMS: not configured</div>
        </div>

        {/* Security */}
        <div className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-all">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-purple-50 text-purple-600">
              <Shield size={18} />
            </div>
            <span className="font-semibold text-gray-700 text-sm">Security</span>
          </div>
          <div className="text-sm text-green-600 flex items-center gap-1"><CheckCircle size={14} /> JWT Auth + RBAC</div>
          <div className="text-xs text-gray-400 mt-1">bcrypt password hashing</div>
        </div>
      </div>

      {/* User Profile */}
      {user && (
        <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
          <h3 className="font-semibold text-gray-700 mb-4">Your Profile</h3>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-brand-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">{user.username?.[0]?.toUpperCase()}</span>
            </div>
            <div>
              <div className="font-semibold text-gray-800">{user.username}</div>
              <div className="text-sm text-gray-500">Role: {user.role_id}</div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Seed RAG Policies', url: '/knowledge', icon: Database },
            { label: 'Run ETL Pipeline', url: '/system', icon: Zap },
            { label: 'View Audit Log', url: '/audit', icon: Shield },
            { label: 'Check System Health', url: '/system', icon: SettingsIcon },
          ].map(action => {
            const Icon = action.icon
            return (
              <button key={action.label} onClick={() => window.location.href = action.url}
                className="flex items-center gap-2 border rounded-lg p-3 hover:bg-brand-50 hover:border-brand-300 transition-all text-sm text-gray-700">
                <Icon size={16} className="text-brand-600" /> {action.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
