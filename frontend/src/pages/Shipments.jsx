import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getShipments } from '../services/api'
import PageHeader from '../components/PageHeader'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'

const STATUSES = ['', 'CREATED','PICKED_UP','IN_TRANSIT','AT_FACILITY','OUT_FOR_DELIVERY','DELIVERED','CANCELLED','EXCEPTION']
const SLA_STATUSES = ['', 'ON_TIME', 'AT_RISK', 'BREACHED']

export default function Shipments() {
  const [shipments, setShipments] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const status = searchParams.get('status') || ''
  const sla = searchParams.get('sla_status') || ''

  useEffect(() => {
    setLoading(true)
    const params = { page, page_size: 20 }
    if (status) params.status = status
    if (sla) params.sla_status = sla
    getShipments(params)
      .then(r => { setShipments(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }, [page, status, sla])

  return (
    <div>
      <PageHeader title="Shipments" subtitle={`${total} total shipments`} />

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select className="border rounded-lg px-3 py-2 text-sm" value={status}
          onChange={e => { setSearchParams({ status: e.target.value, sla_status: sla }); setPage(1) }}>
          {STATUSES.map(s => <option key={s} value={s}>{s || 'All Statuses'}</option>)}
        </select>
        <select className="border rounded-lg px-3 py-2 text-sm" value={sla}
          onChange={e => { setSearchParams({ status, sla_status: e.target.value }); setPage(1) }}>
          {SLA_STATUSES.map(s => <option key={s} value={s}>{s || 'All SLA'}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? <LoadingSpinner /> : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b bg-gray-50">
              {['Shipment ID','Carrier','Origin','Destination','Status','SLA','Priority','Planned Ship'].map(h =>
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>)}
            </tr></thead>
            <tbody>
              {shipments.map(s => (
                <tr key={s.shipment_id} className="border-b hover:bg-blue-50 cursor-pointer"
                  onClick={() => navigate(`/shipments/${s.shipment_id}`)}>
                  <td className="px-4 py-3 font-mono text-xs text-brand-600 font-semibold">{s.shipment_id}</td>
                  <td className="px-4 py-3 text-gray-700">{s.carrier_name}</td>
                  <td className="px-4 py-3 text-gray-500">{s.origin_facility_id}</td>
                  <td className="px-4 py-3 text-gray-500">{s.destination_facility_id}</td>
                  <td className="px-4 py-3"><StatusBadge value={s.status} /></td>
                  <td className="px-4 py-3"><StatusBadge value={s.sla_status} /></td>
                  <td className="px-4 py-3 text-gray-500">{s.priority}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {s.planned_ship_time ? new Date(s.planned_ship_time).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
          <span className="text-xs text-gray-500">Page {page} of {Math.ceil(total/20) || 1}</span>
          <div className="flex gap-2">
            <button disabled={page===1} onClick={() => setPage(p => p-1)}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-40">Prev</button>
            <button disabled={page*20 >= total} onClick={() => setPage(p => p+1)}
              className="px-3 py-1 text-sm border rounded-md disabled:opacity-40">Next</button>
          </div>
        </div>
      </div>
    </div>
  )
}
