import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Label, LabelList
} from 'recharts'
import {
  Package, Truck, CheckCircle, AlertTriangle, Clock,
  BarChart2, Shield, Activity, TrendingUp
} from 'lucide-react'
import { getAnalyticsSummary, getShipments } from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'
import { useAuth } from '../context/AuthContext'

const PIE_COLORS = ['#10B981', '#6366f1', '#F59E0B', '#F43F5E']

const KpiCard = ({ title, value, sub, icon: Icon, grad, to, filter }) => {
  const navigate = useNavigate()
  return (
    <div onClick={() => to && navigate(to + (filter ? `?${filter}` : ''))}
      className={`bg-white rounded-2xl p-5 shadow-card border border-gray-50 cursor-pointer
        hover:-translate-y-1 hover:shadow-card-hover transition-all duration-200`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl ${grad} flex items-center justify-center shadow-lg`}>
          <Icon size={18} className="text-white" />
        </div>
        {sub !== undefined && (
          <span className={`text-xs font-medium flex items-center gap-0.5 ${sub >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
            <TrendingUp size={11} className={sub < 0 ? 'rotate-180' : ''} />
            {Math.abs(sub)}%
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-ink-900 leading-none mb-1">{value ?? '—'}</div>
      <div className="text-xs text-ink-500 font-medium">{title}</div>
    </div>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white rounded-xl shadow-card border border-gray-100 px-3 py-2 text-xs">
      <div className="font-semibold text-ink-900">{payload[0].name}</div>
      <div className="text-ink-500">{payload[0].value} shipments</div>
    </div>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [shipments, setShipments] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { user } = useAuth()

  useEffect(() => {
    Promise.all([getAnalyticsSummary(), getShipments({ page_size: 6 })])
      .then(([s, sh]) => { setSummary(s.data); setShipments(sh.data.items || []) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Loading dashboard..." />

  const total = Number(summary?.total || 0)
  const delivered = Number(summary?.delivered || 0)
  const inTransit = Number(summary?.in_transit || 0)
  const delayed = Number(summary?.delayed || 0)
  const highRisk = Number(summary?.high_risk || 0)
  const atRisk = Math.max(0, highRisk - delayed)

  const pieData = [
    { name: 'Delivered', value: delivered },
    { name: 'In Transit', value: inTransit },
    { name: 'At Risk', value: atRisk },
    { name: 'Breached', value: delayed },
  ].filter(d => d.value > 0)

  const slaData = [
    { name: 'On Time', value: Math.max(0, total - highRisk), pct: total ? Math.round((total - highRisk) / total * 100) : 0, fill: '#6366f1' },
    { name: 'At Risk', value: atRisk, pct: total ? Math.round(atRisk / total * 100) : 0, fill: '#6366f1' },
    { name: 'Breached', value: delayed, pct: total ? Math.round(delayed / total * 100) : 0, fill: '#6366f1' },
  ]

  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })

  return (
    <div className="space-y-5">
      {/* Welcome header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">
            Welcome back, <span className="text-brand-500">{user?.username}!</span>
          </h1>
          <p className="text-ink-500 text-sm mt-0.5">Here's your logistics overview for today.</p>
        </div>
        <div className="hidden md:flex items-center gap-2 bg-white rounded-xl px-4 py-2 text-xs text-ink-500 shadow-soft border border-gray-100">
          <span>📅</span> {today}
        </div>
      </div>

      {/* Row 1 KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="Total Shipments" value={total} sub={12} icon={Package}
          grad="grad-blue" to="/shipments" />
        <KpiCard title="In Transit" value={inTransit} sub={8} icon={Truck}
          grad="grad-purple" to="/shipments" filter="status=IN_TRANSIT" />
        <KpiCard title="Delivered" value={delivered} sub={14} icon={CheckCircle}
          grad="grad-green" to="/shipments" filter="status=DELIVERED" />
        <KpiCard title="SLA Breached" value={delayed} sub={-5} icon={AlertTriangle}
          grad="grad-rose" to="/shipments" filter="sla_status=BREACHED" />
      </div>

      {/* Row 2 KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="High Risk" value={highRisk} sub={7} icon={Activity}
          grad="grad-amber" to="/alerts" />
        <KpiCard title="Avg Delay (h)" value={summary?.avg_delay_hours ?? 0} sub={-3} icon={Clock}
          grad="grad-sky" to="/alerts" />
        <KpiCard title="On-Time %" value={`${summary?.on_time_pct ?? 0}%`} sub={4} icon={BarChart2}
          grad="grad-green" to="/shipments" />
        <KpiCard title="SLA Compliance" value={`${summary?.sla_compliance_pct ?? 0}%`} sub={6} icon={Shield}
          grad="grad-purple" to="/shipments" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Donut chart */}
        <div className="bg-white rounded-2xl shadow-card border border-gray-50 p-6">
          <h3 className="font-semibold text-ink-900 text-sm mb-4">Shipment Status Distribution</h3>
          <div className="flex items-center gap-6">
            <div className="relative">
              <ResponsiveContainer width={200} height={200}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={58} outerRadius={80}
                    paddingAngle={3} dataKey="value"
                    onClick={(e) => navigate(`/shipments?status=${e.name.replace(' ','_').toUpperCase()}`)}>
                    {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} className="cursor-pointer" />)}
                    <Label value={total} position="center" className="text-2xl font-bold"
                      style={{ fontSize: 28, fontWeight: 700, fill: '#172033' }} />
                    <Label value="Total" position="center" dy={20}
                      style={{ fontSize: 11, fill: '#64748B' }} />
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-3">
              {pieData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between cursor-pointer
                  hover:bg-gray-50 rounded-lg px-2 py-1 transition-colors"
                  onClick={() => navigate(`/shipments`)}>
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: PIE_COLORS[i] }} />
                    <span className="text-xs text-ink-700 font-medium">{d.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-ink-900">{d.value}</span>
                    <span className="text-xs text-ink-400 w-7 text-right">{total ? Math.round(d.value/total*100) : 0}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* SLA bar chart */}
        <div className="bg-white rounded-2xl shadow-card border border-gray-50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-ink-900 text-sm">SLA Status Overview</h3>
            <div className="flex gap-1">
              {['7D','30D','90D'].map((t,i) => (
                <button key={t} className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
                  i===0 ? 'grad-blue text-white' : 'text-ink-400 hover:bg-gray-50'}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={slaData} barSize={56}>
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748B' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip cursor={{ fill: 'rgba(99,102,241,0.05)' }}
                content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[8,8,0,0]}
                fill="url(#barGrad)"
                onClick={(d) => navigate(`/shipments?sla_status=${d.name.replace(' ','_').toUpperCase()}`)}>
                <LabelList dataKey="pct" position="top" formatter={v => `${v}%`}
                  style={{ fontSize: 12, fontWeight: 700, fill: '#172033' }} />
              </Bar>
              <defs>
                <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#818cf8" stopOpacity={0.7} />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent shipments */}
      <div className="bg-white rounded-2xl shadow-card border border-gray-50 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-ink-900 text-sm">Recent Shipments</h3>
          <button onClick={() => navigate('/shipments')}
            className="text-xs text-brand-500 font-medium hover:text-brand-600 transition-colors">View all →</button>
        </div>
        <table className="min-w-full text-sm">
          <thead><tr className="border-b border-gray-100">
            {['Shipment ID','Carrier','Status','SLA','Priority'].map(h =>
              <th key={h} className="pb-3 text-left text-xs font-semibold text-ink-400 uppercase tracking-wider first:pl-0 px-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {shipments.map(s => (
              <tr key={s.shipment_id} className="border-b border-gray-50 hover:bg-brand-50/30 cursor-pointer transition-colors"
                onClick={() => navigate(`/shipments/${s.shipment_id}`)}>
                <td className="py-3 px-3 first:pl-0 font-mono text-xs text-brand-500 font-bold">{s.shipment_id}</td>
                <td className="py-3 px-3 text-ink-700 text-xs">{s.carrier_name}</td>
                <td className="py-3 px-3"><StatusBadge value={s.status} /></td>
                <td className="py-3 px-3"><StatusBadge value={s.sla_status} /></td>
                <td className="py-3 px-3 text-ink-400 text-xs">{s.priority}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
