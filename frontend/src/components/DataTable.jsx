import React from 'react'

export default function DataTable({ columns, data, onRowClick, emptyMsg = 'No data' }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            {columns.map(c => (
              <th key={c.key} className="px-4 py-3.5 text-left font-semibold text-ink-500 text-xs uppercase tracking-wider whitespace-nowrap">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr><td colSpan={columns.length} className="text-center py-12 text-ink-300">{emptyMsg}</td></tr>
          ) : data.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-gray-50 transition-colors ${onRowClick ? 'cursor-pointer hover:bg-brand-50/40' : 'hover:bg-gray-50/50'}`}
            >
              {columns.map(c => (
                <td key={c.key} className="px-4 py-3 whitespace-nowrap text-ink-700">
                  {c.render ? c.render(row[c.key], row) : row[c.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
