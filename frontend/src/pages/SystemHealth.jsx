import React, { useEffect, useState } from 'react'
import { getHealth, getHealthDB, getHealthML, getHealthLLM } from '../services/api'
import PageHeader from '../components/PageHeader'
import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react'

const StatusIcon = ({ status }) => {
  if (status === 'healthy' || status === 'available' || status === 'configured')
    return <CheckCircle size={18} className="text-green-500" />
  if (status === 'unhealthy')
    return <XCircle size={18} className="text-red-500" />
  return <AlertTriangle size={18} className="text-yellow-500" />
}

export default function SystemHealth() {
  const [checks, setChecks] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([getHealth(), getHealthDB(), getHealthML(), getHealthLLM()])
      .then(([app, db, ml, llm]) => {
        setChecks({
          app:  app.status === 'fulfilled' ? app.value.data : { status: 'error' },
          db:   db.status === 'fulfilled'  ? db.value.data  : { status: 'error' },
          ml:   ml.status === 'fulfilled'  ? ml.value.data  : { status: 'error' },
          llm:  llm.status === 'fulfilled' ? llm.value.data : { status: 'error' },
        })
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader title="System Health" subtitle="Backend, database, ML and LLM connectivity" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { key: 'app',  label: 'Backend API' },
          { key: 'db',   label: 'PostgreSQL Database' },
          { key: 'ml',   label: 'ML Models' },
          { key: 'llm',  label: 'LLM / Groq' },
        ].map(({ key, label }) => {
          const c = checks[key] || {}
          return (
            <div key={key} className="bg-white rounded-xl border shadow-sm p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-700">{label}</h3>
                {!loading && <StatusIcon status={c.status} />}
              </div>
              <pre className="text-xs text-gray-500 whitespace-pre-wrap break-all bg-gray-50 rounded p-3">
                {loading ? 'Checking...' : JSON.stringify(c, null, 2)}
              </pre>
            </div>
          )
        })}
      </div>
    </div>
  )
}
