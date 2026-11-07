import React from 'react'
import { useNavigate } from 'react-router-dom'

export default function KpiCard({ title, value, subtitle, icon: Icon, color = 'blue', to, filter }) {
  const navigate = useNavigate()
  const gradients = {
    blue:   'grad-blue',
    purple: 'grad-purple',
    green:  'grad-green',
    red:    'grad-rose',
    orange: 'grad-amber',
    yellow: 'grad-amber',
    sky:    'grad-sky',
  }
  const grad = gradients[color] || gradients.blue

  return (
    <div
      onClick={() => to && navigate(to + (filter ? `?${filter}` : ''))}
      className={`bg-white rounded-xl2 shadow-card border border-gray-50 p-5 ${to ? 'cursor-pointer' : ''} card-hover animate-fade-in-up`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-500">{title}</span>
          <span className="text-2xl font-bold text-ink-900">{value ?? '—'}</span>
        </div>
        {Icon && (
          <div className={`w-11 h-11 rounded-2xl ${grad} flex items-center justify-center shadow-lg shrink-0`}>
            <Icon size={20} className="text-white" />
          </div>
        )}
      </div>
      {subtitle && <div className="text-xs text-ink-500 mt-1">{subtitle}</div>}
    </div>
  )
}
