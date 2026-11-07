import React, { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import { getMe, getHealthFull } from '../services/api'
import { Users, Shield, CheckCircle, XCircle } from 'lucide-react'

const ROLES = [
  { id: 'ADMIN', name: 'Administrator', desc: 'Full system access', color: 'bg-red-100 text-red-700' },
  { id: 'PLANNER', name: 'Planner', desc: 'Route and shipment planning', color: 'bg-blue-100 text-blue-700' },
  { id: 'ANALYST', name: 'Analyst', desc: 'Analytics and reporting', color: 'bg-purple-100 text-purple-700' },
  { id: 'OPERATOR', name: 'Operator', desc: 'Warehouse and carrier operations', color: 'bg-green-100 text-green-700' },
  { id: 'MANAGER', name: 'Manager', desc: 'Operations management', color: 'bg-orange-100 text-orange-700' },
]

const ACTORS = [
  { name: 'Supplier', desc: 'Provides goods for shipment', roles: ['OPERATOR'] },
  { name: 'Planner', desc: 'Plans routes and schedules', roles: ['PLANNER'] },
  { name: 'Carrier / Warehouse Operator', desc: 'Executes shipments and manages facilities', roles: ['OPERATOR'] },
  { name: 'Logistics Analyst', desc: 'Analyzes performance and delays', roles: ['ANALYST'] },
  { name: 'Operations Manager', desc: 'Oversees all operations and approvals', roles: ['MANAGER', 'ADMIN'] },
]

export default function UserManagement() {
  const [currentUser, setCurrentUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getMe().then(r => setCurrentUser(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="User Management" subtitle="Roles, permissions, and business actors" />

      {/* Current User */}
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6 hover:shadow-md transition-shadow">
        <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <Users size={18} className="text-brand-600" /> Current User
        </h3>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-brand-600 flex items-center justify-center">
            <span className="text-white font-bold text-lg">{currentUser?.username?.[0]?.toUpperCase() || 'U'}</span>
          </div>
          <div>
            <div className="font-semibold text-gray-800">{currentUser?.username}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded ${ROLES.find(r => r.id === currentUser?.role_id)?.color || 'bg-gray-100'}`}>
                {currentUser?.role_id}
              </span>
              <span className="text-xs text-green-600 flex items-center gap-1">
                <CheckCircle size={12} /> Active
              </span>
              {currentUser?.is_demo && <span className="text-xs text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded">DEMO</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Roles */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {ROLES.map(role => (
          <div key={role.id} className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md hover:border-brand-300 transition-all cursor-pointer">
            <div className="flex items-center gap-2 mb-2">
              <Shield size={18} className="text-gray-400" />
              <span className={`text-xs px-2 py-0.5 rounded ${role.color}`}>{role.id}</span>
            </div>
            <div className="font-semibold text-gray-800">{role.name}</div>
            <div className="text-xs text-gray-500 mt-1">{role.desc}</div>
            {currentUser?.role_id === role.id && (
              <div className="mt-2 text-xs text-brand-600 flex items-center gap-1">
                <CheckCircle size={12} /> Your role
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Business Actors */}
      <div className="bg-white rounded-xl border shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Business Actors</h3>
        <div className="space-y-3">
          {ACTORS.map(actor => (
            <div key={actor.name} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors">
              <Users size={16} className="text-gray-400 mt-0.5 shrink-0" />
              <div>
                <div className="font-medium text-gray-800 text-sm">{actor.name}</div>
                <div className="text-xs text-gray-500">{actor.desc}</div>
                <div className="flex gap-1 mt-1">
                  {actor.roles.map(r => (
                    <span key={r} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{r}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
