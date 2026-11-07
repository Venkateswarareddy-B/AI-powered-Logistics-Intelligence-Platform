import React from 'react'

export default function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-center justify-between mb-6 animate-fade-in-up">
      <div>
        <h1 className="text-xl font-bold text-ink-900 tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-ink-500 mt-0.5">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
