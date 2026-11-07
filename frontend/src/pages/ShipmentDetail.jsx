import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getShipment, getShipmentTracking, getShipmentETA, getShipmentDelayRisk, predictETA } from '../services/api'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import { ArrowLeft, RefreshCw } from 'lucide-react'

export default function ShipmentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [shp, setShp] = useState(null)
  const [events, setEvents] = useState([])
  const [etas, setEtas] = useState([])
  const [risk, setRisk] = useState(null)
  const [loading, setLoading] = useState(true)
  const [predicting, setPredicting] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      getShipment(id), getShipmentTracking(id), getShipmentETA(id), getShipmentDelayRisk(id)
    ]).then(([s, t, e, r]) => {
      setShp(s.data); setEvents(t.data); setEtas(e.data); setRisk(r.data)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  const runPredict = async () => {
    setPredicting(true)
    await predictETA(id)
    const r = await getShipmentDelayRisk(id)
    setRisk(r.data)
    const e = await getShipmentETA(id)
    setEtas(e.data)
    setPredicting(false)
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title={id} subtitle="Shipment Details">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800">
          <ArrowLeft size={14} /> Back
        </button>
        <button onClick={runPredict} disabled={predicting}
          className="flex items-center gap-1 text-sm bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-500 disabled:opacity-50">
          <RefreshCw size={14} className={predicting ? 'animate-spin' : ''} />
          {predicting ? 'Predicting...' : 'Predict ETA'}
        </button>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Shipment info */}
        <div className="md:col-span-2 bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Shipment Information</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              ['Status', <StatusBadge value={shp?.status} />],
              ['SLA Status', <StatusBadge value={shp?.sla_status} />],
              ['Carrier', shp?.carrier_name],
              ['Service Level', shp?.service_level_name],
              ['Priority', shp?.priority],
              ['Origin', `${shp?.origin_name} (${shp?.origin_city})`],
              ['Destination', `${shp?.dest_name} (${shp?.dest_city})`],
              ['Distance', `${shp?.route_distance_km} km`],
              ['Weight', `${shp?.weight_kg ?? '—'} kg`],
              ['Planned Ship', shp?.planned_ship_time ? new Date(shp.planned_ship_time).toLocaleString() : '—'],
              ['Promised Delivery', shp?.promised_delivery_time ? new Date(shp.promised_delivery_time).toLocaleString() : '—'],
              ['Actual Delivery', shp?.actual_delivery_time ? new Date(shp.actual_delivery_time).toLocaleString() : '—'],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="text-gray-400 text-xs mb-0.5">{k}</div>
                <div className="text-gray-800 font-medium">{v ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk */}
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Delay Risk</h3>
          {risk?.delay_probability !== null && risk?.delay_probability !== undefined ? (
            <div>
              <div className="text-4xl font-bold text-center mb-2" style={{
                color: risk.delay_probability > 0.7 ? '#ef4444' : risk.delay_probability > 0.4 ? '#f59e0b' : '#22c55e'
              }}>
                {Math.round(risk.delay_probability * 100)}%
              </div>
              <div className="text-center text-sm text-gray-500 mb-4">Delay Probability</div>
              <div className="text-xs text-gray-400">
                <div>Model: {risk.model_version}</div>
                <div>Predicted ETA: {risk.predicted_eta ? new Date(risk.predicted_eta).toLocaleString() : '—'}</div>
              </div>
            </div>
          ) : <p className="text-gray-400 text-sm">Run "Predict ETA" to calculate.</p>}
        </div>
      </div>

      {/* Tracking events */}
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <h3 className="font-semibold text-gray-700 mb-4">Tracking Timeline ({events.length} events)</h3>
        <div className="space-y-3">
          {events.map((ev, i) => (
            <div key={ev.event_id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className={`w-3 h-3 rounded-full mt-1 ${ev.is_duplicate ? 'bg-red-400' : ev.is_late_arrival ? 'bg-yellow-400' : 'bg-brand-500'}`} />
                {i < events.length - 1 && <div className="w-0.5 flex-1 bg-gray-200 mt-1" />}
              </div>
              <div className="pb-4 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-semibold text-sm text-gray-800">{ev.event_type?.replace(/_/g,' ')}</span>
                  {ev.is_duplicate && <span className="text-xs text-red-500 bg-red-50 px-1 rounded">DUPLICATE</span>}
                  {ev.is_late_arrival && <span className="text-xs text-yellow-600 bg-yellow-50 px-1 rounded">LATE SCAN</span>}
                </div>
                <div className="text-xs text-gray-400">
                  {ev.event_time ? new Date(ev.event_time).toLocaleString() : '—'} · {ev.facility_name || ev.facility_id || 'En route'} · {ev.source}
                </div>
                {ev.description && <div className="text-xs text-gray-500 mt-0.5">{ev.description}</div>}
              </div>
            </div>
          ))}
          {events.length === 0 && <p className="text-gray-400 text-sm">No tracking events yet.</p>}
        </div>
      </div>

      {/* ETA History */}
      {etas.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold text-gray-700 mb-4">ETA Prediction History</h3>
          <table className="min-w-full text-sm">
            <thead><tr className="border-b bg-gray-50">
              {['Prediction Time','Predicted ETA','Delay Prob','Model','Type'].map(h =>
                <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500">{h}</th>)}
            </tr></thead>
            <tbody>
              {etas.map(e => (
                <tr key={e.eta_estimate_id} className="border-b">
                  <td className="px-3 py-2 text-xs">{new Date(e.prediction_time).toLocaleString()}</td>
                  <td className="px-3 py-2 text-xs">{new Date(e.predicted_eta).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    <span className={`font-semibold ${Number(e.delay_probability) > 0.7 ? 'text-red-500' : Number(e.delay_probability) > 0.4 ? 'text-yellow-500' : 'text-green-500'}`}>
                      {e.delay_probability !== null ? `${Math.round(Number(e.delay_probability)*100)}%` : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500">{e.model_version}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{e.model_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
