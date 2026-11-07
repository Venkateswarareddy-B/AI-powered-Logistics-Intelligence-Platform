import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import PageHeader from '../components/PageHeader'
import DemoBanner from '../components/DemoBanner'
import LoadingSpinner from '../components/LoadingSpinner'
import { getAnalyticsSummary, getShipments, getDelays, getCarriers } from '../services/api'
import { FileBarChart, Download, TrendingUp, AlertTriangle, Truck, Package } from 'lucide-react'

export default function Reports() {
  const [summary, setSummary] = useState(null)
  const [delays, setDelays] = useState([])
  const [carriers, setCarriers] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      getAnalyticsSummary(),
      getDelays(),
      getCarriers(),
    ]).then(([s, d, c]) => {
      setSummary(s.data)
      setDelays(d.data)
      setCarriers(c.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Generating reports..." />

  // Build shipment status chart data
  const statusData = summary ? [
    { name: 'Delivered', value: Number(summary.delivered || 0), fill: '#22c55e' },
    { name: 'In Transit', value: Number(summary.in_transit || 0), fill: '#3b82f6' },
    { name: 'Delayed', value: Number(summary.delayed || 0), fill: '#ef4444' },
  ].filter(d => d.value > 0) : []

  // Build SLA chart data
  const slaData = summary ? [
    { name: 'On Time', value: Number(summary.total || 0) - Number(summary.high_risk || 0), fill: '#22c55e' },
    { name: 'At Risk', value: Math.max(0, Number(summary.high_risk || 0) - Number(summary.delayed || 0)), fill: '#f59e0b' },
    { name: 'Breached', value: Number(summary.delayed || 0), fill: '#ef4444' },
  ].filter(d => d.value > 0) : []

  // Delay reasons from delays list
  const delayReasons = {}
  delays.forEach(d => {
    const reason = d.sla_status || 'Unknown'
    delayReasons[reason] = (delayReasons[reason] || 0) + 1
  })
  const delayReasonData = Object.entries(delayReasons).map(([name, value]) => ({ name, value }))

  return (
    <div>
      <PageHeader title="Reports" subtitle="Analytical reports and operational insights">
        <button onClick={() => window.print()}
          className="flex items-center gap-1 text-sm border rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors">
          <Download size={14} /> Export
        </button>
      </PageHeader>
      <DemoBanner />

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Shipments', value: summary?.total, icon: Package, color: 'blue' },
          { label: 'Delivered', value: summary?.delivered, icon: Truck, color: 'green' },
          { label: 'SLA Breached', value: summary?.delayed, icon: AlertTriangle, color: 'red' },
          { label: 'On-Time %', value: `${summary?.on_time_pct}%`, icon: TrendingUp, color: 'green' },
        ].map((kpi, i) => {
          const Icon = kpi.icon
          const colors = { blue: 'bg-blue-50 text-blue-600', green: 'bg-green-50 text-green-600', red: 'bg-red-50 text-red-600' }
          return (
            <div key={i} className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => kpi.label.includes('SLA') ? navigate('/alerts') : navigate('/shipments')}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-gray-500 font-medium">{kpi.label}</span>
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colors[kpi.color]}`}>
                  <Icon size={18} />
                </div>
              </div>
              <div className="text-2xl font-bold text-gray-900">{kpi.value ?? '—'}</div>
            </div>
          )
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Shipment Status */}
        <div className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <FileBarChart size={16} className="text-brand-600" /> Shipment Status Distribution
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={statusData}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
              <Bar dataKey="value" radius={[6,6,0,0]} onClick={(d) => navigate(`/shipments?status=${d.name.replace(' ','_').toUpperCase()}`)} className="cursor-pointer">
                {statusData.map((entry, i) => <Bar key={i} dataKey="value" fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* SLA Compliance */}
        <div className="bg-white rounded-xl border shadow-sm p-5 hover:shadow-md transition-shadow">
          <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <TrendingUp size={16} className="text-brand-600" /> SLA Compliance Breakdown
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={slaData}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
              <Bar dataKey="value" radius={[6,6,0,0]} onClick={(d) => navigate(`/shipments?sla_status=${d.name.replace(' ','_').toUpperCase()}`)} className="cursor-pointer">
                {slaData.map((entry, i) => <Bar key={i} dataKey="value" fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Carrier Performance Table */}
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <h3 className="font-semibold text-gray-700 mb-4">Carrier Summary ({carriers.length} carriers)</h3>
        <table className="min-w-full text-sm">
          <thead><tr className="border-b bg-gray-50">
            {['Carrier', 'Code', 'Active', 'Delay Factor'].map(h =>
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
          </tr></thead>
          <tbody>
            {carriers.map(c => (
              <tr key={c.carrier_id} className="border-b hover:bg-brand-50 cursor-pointer transition-colors"
                onClick={() => navigate('/carriers')}>
                <td className="px-4 py-3 text-gray-800 font-medium">{c.carrier_name}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{c.carrier_code}</td>
                <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{c.is_active ? 'Active' : 'Inactive'}</span></td>
                <td className="px-4 py-3 text-gray-500">{c.base_delay_factor}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delay Report */}
      <div className="bg-white rounded-xl border shadow-sm p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Delay Report ({delays.length} shipments)</h3>
        <table className="min-w-full text-sm">
          <thead><tr className="border-b bg-gray-50">
            {['Shipment', 'Carrier', 'SLA', 'Priority', 'Delay (h)', 'Promised'].map(h =>
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
          </tr></thead>
          <tbody>
            {delays.slice(0, 20).map(d => (
              <tr key={d.shipment_id} className="border-b hover:bg-red-50 cursor-pointer transition-colors"
                onClick={() => navigate(`/shipments/${d.shipment_id}`)}>
                <td className="px-4 py-3 font-mono text-xs text-brand-600">{d.shipment_id}</td>
                <td className="px-4 py-3 text-gray-700">{d.carrier_name}</td>
                <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded ${d.sla_status === 'BREACHED' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{d.sla_status}</span></td>
                <td className="px-4 py-3 text-gray-500">{d.priority}</td>
                <td className="px-4 py-3 font-semibold text-red-600">{d.delay_hours ?? '—'}</td>
                <td className="px-4 py-3 text-gray-400 text-xs">{d.promised_delivery_time ? new Date(d.promised_delivery_time).toLocaleString() : '—'}</td>
              </tr>
            ))}
            {delays.length === 0 && <tr><td colSpan={6} className="text-center py-8 text-gray-400">No delayed shipments</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
