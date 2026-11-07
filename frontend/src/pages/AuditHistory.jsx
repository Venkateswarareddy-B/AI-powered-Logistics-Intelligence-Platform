import React, { useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import { getAuditLogs } from '../services/api'
import { History, Filter } from 'lucide-react'

export default function AuditHistory() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params = { limit: 100 }
      if (actionFilter) params.action = actionFilter
      const r = await getAuditLogs(params)
      setLogs(r.data)
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [actionFilter])

  const actionColors = {
    APPROVAL_APPROVED: 'bg-green-100 text-green-700',
    APPROVAL_REJECTED: 'bg-red-100 text-red-700',
    APPROVAL_REQUESTED: 'bg-yellow-100 text-yellow-700',
    SLA_STATUS_CHANGE: 'bg-blue-100 text-blue-700',
    APPROVAL_MORE_INFO_REQUESTED: 'bg-orange-100 text-orange-700',
  }

  return (
    <div>
      <PageHeader title="Audit History" subtitle="Immutable record of all system operations">
        <select className="border rounded-lg px-3 py-1.5 text-sm" value={actionFilter}
          onChange={e => setActionFilter(e.target.value)}>
          <option value="">All actions</option>
          <option value="APPROVAL_APPROVED">Approvals</option>
          <option value="APPROVAL_REJECTED">Rejections</option>
          <option value="APPROVAL_REQUESTED">Requests</option>
          <option value="SLA_STATUS_CHANGE">SLA Changes</option>
        </select>
      </PageHeader>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? <LoadingSpinner /> : logs.length === 0 ? (
          <div className="text-center py-10 text-gray-400">
            <History size={32} className="mx-auto mb-2 opacity-50" />
            <div>No audit logs found</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead><tr className="border-b bg-gray-50">
                {['Action', 'Entity', 'Decision', 'Reason', 'User', 'Timestamp'].map(h =>
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
              </tr></thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.audit_id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded ${actionColors[log.action] || 'bg-gray-100 text-gray-600'}`}>
                        {log.action?.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{log.entity_type}:{log.entity_id?.slice(0, 20)}</td>
                    <td className="px-4 py-3 text-gray-700 text-xs">{log.decision || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-xs truncate">{log.reason || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{log.user_id?.slice(0, 12) || 'system'}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{log.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
