import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDelays } from '../services/api'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'

export default function DelayAlerts() {
  const [delays, setDelays] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getDelays().then(r => setDelays(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Delay Alerts" subtitle={`${delays.length} shipments with SLA issues`} />
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="min-w-full text-sm">
          <thead><tr className="border-b bg-gray-50">
            {['Shipment','Carrier','SLA Status','Status','Priority','Delay (h)','Promised Delivery'].map(h =>
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
          </tr></thead>
          <tbody>
            {delays.map(d => (
              <tr key={d.shipment_id} className="border-b hover:bg-red-50 cursor-pointer"
                onClick={() => navigate(`/shipments/${d.shipment_id}`)}>
                <td className="px-4 py-3 font-mono text-xs text-brand-600 font-semibold">{d.shipment_id}</td>
                <td className="px-4 py-3 text-gray-700">{d.carrier_name}</td>
                <td className="px-4 py-3"><StatusBadge value={d.sla_status} /></td>
                <td className="px-4 py-3"><StatusBadge value={d.status} /></td>
                <td className="px-4 py-3 text-gray-500">{d.priority}</td>
                <td className="px-4 py-3 font-semibold text-red-600">{d.delay_hours ?? '—'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {d.promised_delivery_time ? new Date(d.promised_delivery_time).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
            {delays.length === 0 && (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400">No delay alerts found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
