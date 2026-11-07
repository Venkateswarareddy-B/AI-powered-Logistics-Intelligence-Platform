import React from 'react'
export default function DemoBanner() {
  return (
    <div className="bg-amber-50 border border-amber-200/60 text-amber-700 text-xs px-4 py-2.5 rounded-xl mb-5 flex items-center gap-2 font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
      <span>DEMO DATA — All shipment, carrier and facility data is synthetic. Not real logistics information.</span>
    </div>
  )
}
