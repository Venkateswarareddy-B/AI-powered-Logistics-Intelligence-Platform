import React, { useEffect, useState } from 'react'
import { getCarriers, getCarrierPerformance } from '../services/api'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function Carriers() {
  const [carriers, setCarriers] = useState([])
  const [selected, setSelected] = useState(null)
  const [perf, setPerf] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCarriers().then(r => setCarriers(r.data)).finally(() => setLoading(false))
  }, [])

  const selectCarrier = async (c) => {
    setSelected(c)
    setPerf(null)
    try { const r = await getCarrierPerformance(c.carrier_id); setPerf(r.data) } catch {}
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Carrier Analytics" subtitle="Performance metrics derived from shipment history" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border shadow-sm p-4">
          <h3 className="font-semibold text-gray-700 mb-3 text-sm">Carriers ({carriers.length})</h3>
          <div className="space-y-1">
            {carriers.map(c => (
              <div key={c.carrier_id} onClick={() => selectCarrier(c)}
                className={`px-3 py-2 rounded-lg cursor-pointer text-sm ${selected?.carrier_id===c.carrier_id ? 'bg-brand-50 text-brand-700 border border-brand-200' : 'hover:bg-gray-50 text-gray-700'}`}>
                <div className="font-medium">{c.carrier_name}</div>
                <div className="text-xs text-gray-400">{c.carrier_code}</div>
              </div>
            ))}
          </div>
        </div>

        {selected && (
          <div className="md:col-span-2 bg-white rounded-xl border shadow-sm p-5">
            <h3 className="font-semibold text-gray-700 mb-4">{selected.carrier_name}</h3>
            {perf ? (
              <div>
                <div className="grid grid-cols-3 gap-4 mb-6">
                  {[
                    ['On-Time Rate', `${Math.round((perf.on_time_rate||0)*100)}%`],
                    ['Avg Delay (h)', perf.average_delay_hours ?? '—'],
                    ['Carrier Score', perf.carrier_score ?? '—'],
                    ['Total Shipments', perf.total_shipments],
                    ['Late Scan Rate', `${Math.round((perf.late_scan_rate||0)*100)}%`],
                    ['Route Change Rate', `${Math.round((perf.route_change_rate||0)*100)}%`],
                  ].map(([k,v]) => (
                    <div key={k} className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs text-gray-400 mb-1">{k}</div>
                      <div className="text-lg font-bold text-gray-800">{v}</div>
                    </div>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={[
                    { name: 'On Time %', value: Math.round((perf.on_time_rate||0)*100) },
                    { name: 'Late Scan %', value: Math.round((perf.late_scan_rate||0)*100) },
                    { name: 'Route Chg %', value: Math.round((perf.route_change_rate||0)*100) },
                    { name: 'Score', value: Number(perf.carrier_score||0) },
                  ]}>
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" radius={[3,3,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <p className="text-gray-400 text-sm">No performance data available. Run the ETL pipeline first.</p>}
          </div>
        )}
      </div>
    </div>
  )
}
