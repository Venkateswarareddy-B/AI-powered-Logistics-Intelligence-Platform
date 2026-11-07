import React, { useEffect, useState } from 'react'
import { getFacilities, getFacilityQueue } from '../services/api'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function Facilities() {
  const [facilities, setFacilities] = useState([])
  const [selected, setSelected] = useState(null)
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFacilities().then(r => setFacilities(r.data)).finally(() => setLoading(false))
  }, [])

  const selectFacility = async (f) => {
    setSelected(f)
    const r = await getFacilityQueue(f.facility_id)
    setQueue(r.data.map(q => ({
      time: new Date(q.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),
      util: Number(q.utilization_pct),
      queue: q.queue_length,
    })).reverse())
  }

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <PageHeader title="Facility Analytics" subtitle="Queue utilization and congestion trends" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border shadow-sm p-4">
          <h3 className="font-semibold text-gray-700 mb-3 text-sm">Facilities ({facilities.length})</h3>
          <div className="space-y-1">
            {facilities.map(f => (
              <div key={f.facility_id} onClick={() => selectFacility(f)}
                className={`px-3 py-2 rounded-lg cursor-pointer text-sm ${selected?.facility_id===f.facility_id ? 'bg-brand-50 text-brand-700 border border-brand-200' : 'hover:bg-gray-50 text-gray-700'}`}>
                <div className="font-medium">{f.facility_name}</div>
                <div className="text-xs text-gray-400">{f.facility_type} · {f.city} · Cap {f.capacity}</div>
              </div>
            ))}
          </div>
        </div>

        {selected && (
          <div className="md:col-span-2 bg-white rounded-xl border shadow-sm p-5">
            <h3 className="font-semibold text-gray-700 mb-2">{selected.facility_name}</h3>
            <div className="text-xs text-gray-400 mb-4">{selected.city}, {selected.state} · {selected.facility_type}</div>
            {queue.length > 0 ? (
              <>
                <h4 className="text-sm font-medium text-gray-600 mb-3">Queue Utilization Trend (last 48 snapshots)</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={queue}>
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} interval={5} />
                    <YAxis domain={[0,100]} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v) => [`${v}%`, 'Utilization']} />
                    <Line type="monotone" dataKey="util" stroke="#3b82f6" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
                <div className="mt-3 text-xs text-gray-400">
                  Latest utilization: <strong className="text-gray-700">{queue[queue.length-1]?.util}%</strong> · Queue length: <strong className="text-gray-700">{queue[queue.length-1]?.queue}</strong>
                </div>
              </>
            ) : <p className="text-gray-400 text-sm">No queue data available.</p>}
          </div>
        )}
      </div>
    </div>
  )
}
