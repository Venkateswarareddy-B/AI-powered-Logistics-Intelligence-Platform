import React, { useEffect, useState } from 'react'
import { getShipments, predictETA, getShipmentDelayRisk } from '../services/api'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

export default function ETAPrediction() {
  const [shipments, setShipments] = useState([])
  const [results, setResults] = useState({})
  const [loading, setLoading] = useState(true)
  const [predicting, setPredicting] = useState({})

  useEffect(() => {
    getShipments({ status: 'IN_TRANSIT', page_size: 30 })
      .then(r => setShipments(r.data.items || []))
      .finally(() => setLoading(false))
  }, [])

  const predict = async (sid) => {
    setPredicting(p => ({ ...p, [sid]: true }))
    try {
      const r = await predictETA(sid)
      setResults(res => ({ ...res, [sid]: r.data }))
    } catch (e) {
      setResults(res => ({ ...res, [sid]: { error: 'Failed' } }))
    } finally {
      setPredicting(p => ({ ...p, [sid]: false }))
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="ETA Prediction" subtitle="Rule-based ETA engine for active shipments" />
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="min-w-full text-sm">
          <thead><tr className="border-b bg-gray-50">
            {['Shipment','Carrier','SLA','Action','Result'].map(h =>
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
          </tr></thead>
          <tbody>
            {shipments.map(s => {
              const r = results[s.shipment_id]
              return (
                <tr key={s.shipment_id} className="border-b">
                  <td className="px-4 py-3 font-mono text-xs text-brand-600">{s.shipment_id}</td>
                  <td className="px-4 py-3 text-gray-700">{s.carrier_name}</td>
                  <td className="px-4 py-3"><StatusBadge value={s.sla_status} /></td>
                  <td className="px-4 py-3">
                    <button onClick={() => predict(s.shipment_id)}
                      disabled={predicting[s.shipment_id]}
                      className="text-xs bg-brand-600 text-white px-2 py-1 rounded hover:bg-brand-500 disabled:opacity-50">
                      {predicting[s.shipment_id] ? 'Running...' : 'Predict'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {r?.error ? <span className="text-red-500">{r.error}</span> :
                     r ? <span className="text-green-600">
                       ETA: {new Date(r.predicted_eta).toLocaleString()} · Risk: {Math.round(r.delay_probability*100)}%
                     </span> : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              )
            })}
            {shipments.length === 0 && (
              <tr><td colSpan={5} className="text-center py-10 text-gray-400">No active shipments</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
