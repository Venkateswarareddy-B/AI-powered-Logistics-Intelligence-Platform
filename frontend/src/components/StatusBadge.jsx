import React from 'react'

const MAP = {
  DELIVERED:        'bg-emerald-50 text-emerald-600 border border-emerald-100',
  IN_TRANSIT:       'bg-brand-50 text-brand-500 border border-brand-100',
  PICKED_UP:        'bg-indigo-50 text-indigo-600 border border-indigo-100',
  AT_FACILITY:      'bg-amber-50 text-amber-600 border border-amber-100',
  OUT_FOR_DELIVERY: 'bg-purple-50 text-purple-600 border border-purple-100',
  CREATED:          'bg-gray-50 text-gray-500 border border-gray-100',
  CANCELLED:        'bg-gray-100 text-gray-400 border border-gray-200',
  EXCEPTION:        'bg-rose-50 text-rose-600 border border-rose-100',
  ON_TIME:          'bg-emerald-50 text-emerald-600 border border-emerald-100',
  AT_RISK:          'bg-amber-50 text-amber-600 border border-amber-100',
  BREACHED:         'bg-rose-50 text-rose-600 border border-rose-100',
  OPEN:             'bg-rose-50 text-rose-600 border border-rose-100',
  ACKNOWLEDGED:     'bg-amber-50 text-amber-600 border border-amber-100',
  RESOLVED:         'bg-emerald-50 text-emerald-600 border border-emerald-100',
}

export default function StatusBadge({ value }) {
  const cls = MAP[value] || 'bg-gray-50 text-gray-500 border border-gray-100'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-medium ${cls}`}>
      {value?.replace(/_/g, ' ')}
    </span>
  )
}
