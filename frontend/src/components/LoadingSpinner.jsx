import React from 'react'
export default function LoadingSpinner({ text = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-ink-300">
      <div className="w-10 h-10 border-3 border-brand-500/20 border-t-brand-500 rounded-full animate-spin mb-4" style={{ borderWidth: '3px' }} />
      <span className="text-sm text-ink-500">{text}</span>
    </div>
  )
}
