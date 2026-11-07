import React, { useState } from 'react'
import PageHeader from '../components/PageHeader'
import { compareRoutes, getShipments, getFacilities } from '../services/api'
import { Send, CheckCircle, XCircle, ArrowRight } from 'lucide-react'

export default function RouteOptimization() {
  const [shipmentId, setShipmentId] = useState('')
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const loadShipments = async () => {
    const r = await getShipments({ page_size: 50, status: 'IN_TRANSIT' })
    setShipments(r.data.items || [])
  }

  React.useEffect(() => { loadShipments() }, [])

  const runCompare = async () => {
    if (!shipmentId) return
    setLoading(true)
    setResult(null)
    try {
      const r = await compareRoutes(shipmentId)
      setResult(r.data)
    } catch (e) {
      setResult({ error: e.response?.data?.detail || 'Failed to compare routes' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <PageHeader title="Route Optimization" subtitle="What-if route comparison and analysis" />
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <h3 className="font-semibold text-gray-700 mb-3">Select Shipment</h3>
        <div className="flex gap-3">
          <select className="border rounded-lg px-3 py-2 text-sm flex-1"
            value={shipmentId} onChange={e => setShipmentId(e.target.value)}>
            <option value="">Choose a shipment...</option>
            {shipments.map(s => (
              <option key={s.shipment_id} value={s.shipment_id}>
                {s.shipment_id} — {s.carrier_name} ({s.status})
              </option>
            ))}
          </select>
          <button onClick={runCompare} disabled={loading || !shipmentId}
            className="flex items-center gap-1 bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-500 disabled:opacity-50 text-sm">
            <Send size={14} /> {loading ? 'Analyzing...' : 'Compare Routes'}
          </button>
        </div>
      </div>

      {result?.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm mb-6">
          {result.error}
        </div>
      )}

      {result && !result.error && (
        <div className="space-y-6">
          {/* Current Route */}
          {result.current_route && (
            <div className="bg-white rounded-xl border shadow-sm p-5">
              <h3 className="font-semibold text-gray-700 mb-4">Current Route</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Route</div>
                  <div className="font-medium text-gray-800">{result.current_route.route_name}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Distance</div>
                  <div className="font-medium text-gray-800">{result.current_route.distance_km} km</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Est. Delivery</div>
                  <div className="font-medium text-gray-800">{result.current_route.estimated_delivery_hours} h</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Cost</div>
                  <div className="font-medium text-gray-800">₹{result.current_route.cost}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Delay Probability</div>
                  <div className="font-medium text-gray-800">{Math.round(result.current_route.delay_probability * 100)}%</div>
                </div>
              </div>
            </div>
          )}

          {/* Alternatives */}
          {result.alternatives && result.alternatives.length > 0 ? (
            <div className="bg-white rounded-xl border shadow-sm p-5">
              <h3 className="font-semibold text-gray-700 mb-4">Alternative Routes</h3>
              <div className="space-y-3">
                {result.alternatives.map((alt, i) => (
                  <div key={i} className={`border rounded-lg p-4 ${i === 0 ? 'border-green-300 bg-green-50' : 'border-gray-200'}`}>
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-gray-800">{alt.route_name}</span>
                      {i === 0 && result.recommendation && (
                        <span className="text-xs bg-green-600 text-white px-2 py-0.5 rounded">RECOMMENDED</span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                      <div><span className="text-gray-400">ETA:</span> <strong>{alt.estimated_delivery_hours}h</strong></div>
                      <div><span className="text-gray-400">Risk:</span> <strong>{Math.round(alt.delay_probability * 100)}%</strong></div>
                      <div><span className="text-gray-400">Cost:</span> <strong>₹{alt.cost}</strong></div>
                      <div><span className="text-gray-400">Time saved:</span> <strong className={alt.time_saved_hours > 0 ? 'text-green-600' : 'text-red-500'}>{alt.time_saved_hours}h</strong></div>
                      <div><span className="text-gray-400">Risk reduction:</span> <strong className={alt.risk_reduction > 0 ? 'text-green-600' : 'text-red-500'}>{Math.round(alt.risk_reduction * 100)}pp</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border shadow-sm p-5 text-center text-gray-400">
              No alternative routes found for this shipment's destination.
            </div>
          )}

          {/* Recommendation */}
          {result.recommendation && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
              <h3 className="font-semibold text-blue-800 mb-2">Recommendation</h3>
              <p className="text-blue-700 text-sm mb-2">{result.recommendation.reason}</p>
              <p className="text-xs text-blue-500">
                {result.simulation_note} · Approval required for route changes.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
