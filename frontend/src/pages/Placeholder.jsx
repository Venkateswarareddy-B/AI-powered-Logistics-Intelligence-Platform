import React from 'react'
import PageHeader from '../components/PageHeader'

export default function Placeholder({ title, description, phase }) {
  return (
    <div>
      <PageHeader title={title} />
      <div className="bg-white rounded-xl border shadow-sm p-10 text-center">
        <div className="text-6xl mb-4">🚧</div>
        <h2 className="text-xl font-semibold text-gray-700 mb-2">{title}</h2>
        <p className="text-gray-500 max-w-md mx-auto">{description}</p>
        {phase && (
          <div className="mt-4 inline-block bg-blue-50 text-blue-700 text-sm px-3 py-1 rounded-full">
            Coming in {phase}
          </div>
        )}
      </div>
    </div>
  )
}
