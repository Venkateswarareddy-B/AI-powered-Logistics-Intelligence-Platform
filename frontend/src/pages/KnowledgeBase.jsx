import React, { useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import { getRagDocuments, seedRagSamples, searchRag, reingestRagDoc, deactivateRagDoc, getWebSources, addWebSource, ingestWebSource, deleteWebSource } from '../services/api'
import { Search, RefreshCw, Archive, FileText, Globe, Plus, Trash2, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react'

const StatusDot = ({ s }) => {
  const m = { ACTIVE:'bg-emerald-500', COMPLETED:'bg-emerald-500', PENDING:'bg-amber-500', PROCESSING:'bg-blue-500 animate-pulse', FAILED:'bg-rose-500', ARCHIVED:'bg-gray-300' }
  return <span className={`inline-block w-2 h-2 rounded-full ${m[s] || 'bg-gray-300'} mr-1.5`} />
}

const TAG = ({ s }) => {
  const m = {
    ACTIVE: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    COMPLETED: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    PENDING: 'bg-amber-50 text-amber-600 border-amber-100',
    PROCESSING: 'bg-blue-50 text-blue-600 border-blue-100',
    FAILED: 'bg-rose-50 text-rose-600 border-rose-100',
    ARCHIVED: 'bg-gray-50 text-gray-500 border-gray-100',
  }
  return <span className={`inline-flex items-center text-xs px-2.5 py-0.5 rounded-lg border ${m[s] || 'bg-gray-50 text-gray-500'}`}>
    <StatusDot s={s} />{s}
  </span>
}

const CATEGORIES = ['LOGISTICS','TRANSPORTATION','SUPPLY_CHAIN','WAREHOUSE_MGMT','FLEET_MGMT','SHIPPING_REGULATIONS','CARRIER_DOCS','ETA_TRACKING','INDUSTRY_KNOWLEDGE','SLA_POLICY','CARRIER_POLICY','WEATHER_SOP','FACILITY_SOP','DELAY_HANDLING','ROUTE_CHANGE','ESCALATION','OTHER']

export default function KnowledgeBase() {
  const [tab, setTab] = useState('docs')
  const [docs, setDocs] = useState([])
  const [webSources, setWebSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [addUrl, setAddUrl] = useState('')
  const [addName, setAddName] = useState('')
  const [addCat, setAddCat] = useState('LOGISTICS')
  const [adding, setAdding] = useState(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [dr, wr] = await Promise.all([getRagDocuments(), getWebSources()])
      setDocs(dr.data); setWebSources(wr.data)
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { loadAll() }, [])

  const seed = async () => { await seedRagSamples(); loadAll() }

  const search = async () => {
    if (!query.trim()) return
    setSearching(true)
    try { const r = await searchRag(query, 5); setSearchResults(r.data) }
    catch {} finally { setSearching(false) }
  }

  const handleAddSource = async (e) => {
    e.preventDefault()
    if (!addUrl || !addName) return
    setAdding(true)
    try {
      const r = await addWebSource({ source_name: addName, url: addUrl, category: addCat })
      setAddUrl(''); setAddName('')
      loadAll()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add source')
    } finally { setAdding(false) }
  }

  const activeCount = docs.filter(d => d.processing_status === 'ACTIVE').length
  const totalChunks = docs.reduce((s, d) => s + (d.chunk_count || 0), 0)

  return (
    <div>
      <PageHeader title="Knowledge Base" subtitle="Manage policies, documents and website sources">
        <button onClick={seed} className="flex items-center gap-1.5 text-xs bg-brand-500 text-white px-3 py-2 rounded-xl hover:bg-brand-600 transition-colors shadow-md">
          <RefreshCw size={13} /> Seed Policies
        </button>
      </PageHeader>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        {[
          { label: 'Documents', value: docs.length, icon: FileText, color: 'text-brand-500 bg-brand-50' },
          { label: 'Web Sources', value: webSources.length, icon: Globe, color: 'text-purple-500 bg-purple-50' },
          { label: 'Total Chunks', value: totalChunks, icon: Search, color: 'text-emerald-500 bg-emerald-50' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-2xl shadow-card border border-gray-50 p-4 flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${s.color}`}>
              <s.icon size={18} />
            </div>
            <div>
              <div className="text-lg font-bold text-ink-900">{s.value}</div>
              <div className="text-xs text-ink-500">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="bg-white rounded-2xl shadow-card border border-gray-50 p-5 mb-5">
        <h3 className="font-semibold text-ink-900 text-sm mb-3">Semantic Search</h3>
        <div className="flex gap-2">
          <div className="flex-1 flex items-center gap-2 border border-gray-100 rounded-xl px-3 bg-surface focus-within:border-brand-400 transition-colors">
            <Search size={15} className="text-ink-300" />
            <input className="flex-1 bg-transparent text-sm outline-none py-2.5 placeholder:text-ink-300"
              value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && search()}
              placeholder="Search knowledge base... e.g. SLA policy for delays" />
          </div>
          <button onClick={search} disabled={searching}
            className="grad-blue text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 shadow-md hover:opacity-90 transition-opacity">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
        {searchResults && (
          <div className="mt-4">
            <div className="text-xs text-ink-400 mb-2">{searchResults.results_count} result(s) found</div>
            {searchResults.citations?.length > 0 ? (
              <div className="space-y-2">
                {searchResults.citations.map((c, i) => (
                  <div key={i} className="border border-gray-100 rounded-xl p-3 bg-surface">
                    <div className="flex items-center gap-2 mb-1">
                      <FileText size={13} className="text-brand-500" />
                      <span className="font-semibold text-xs text-ink-900">{c.document_name}</span>
                      <span className="text-xs text-ink-400">v{c.version} · {c.category}</span>
                      <span className="ml-auto text-xs text-ink-300">chunk {c.chunk_index+1}/{c.chunk_total}</span>
                    </div>
                    <p className="text-xs text-ink-600 line-clamp-3">{c.source_excerpt}</p>
                  </div>
                ))}
              </div>
            ) : <div className="text-sm text-ink-400 bg-surface rounded-lg p-3">No matching content found.</div>}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-surface rounded-xl p-1 w-fit">
        {[['docs','Documents'], ['web','Website Sources']].map(([k, v]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === k ? 'bg-white shadow-soft text-ink-900' : 'text-ink-500 hover:text-ink-700'}`}>
            {v} {k === 'docs' ? `(${docs.length})` : `(${webSources.length})`}
          </button>
        ))}
      </div>

      {/* Documents tab */}
      {tab === 'docs' && (
        <div className="bg-white rounded-2xl shadow-card border border-gray-50 overflow-hidden">
          {loading ? <div className="p-8"><LoadingSpinner /></div> : (
            <table className="min-w-full text-sm">
              <thead><tr className="border-b border-gray-100">
                {['Document','Category','Status','Chunks','Actions'].map(h =>
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-ink-400 uppercase tracking-wider">{h}</th>)}
              </tr></thead>
              <tbody>
                {docs.map(d => (
                  <tr key={d.document_id} className="border-b border-gray-50 hover:bg-brand-50/30 transition-colors">
                    <td className="px-4 py-3 font-medium text-ink-900 text-sm">{d.document_name}</td>
                    <td className="px-4 py-3 text-xs text-ink-500">{d.category}</td>
                    <td className="px-4 py-3"><TAG s={d.processing_status} /></td>
                    <td className="px-4 py-3 text-ink-500">{d.chunk_count || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => reingestRagDoc(d.document_id).then(loadAll)}
                          className="w-7 h-7 rounded-lg bg-brand-50 text-brand-500 hover:bg-brand-100 flex items-center justify-center transition-colors" title="Re-ingest">
                          <RefreshCw size={13} />
                        </button>
                        {d.is_active && (
                          <button onClick={() => deactivateRagDoc(d.document_id).then(loadAll)}
                            className="w-7 h-7 rounded-lg bg-gray-50 text-gray-400 hover:bg-rose-50 hover:text-rose-500 flex items-center justify-center transition-colors" title="Deactivate">
                            <Archive size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {docs.length === 0 && (
                  <tr><td colSpan={5} className="text-center py-12 text-ink-300">
                    <FileText size={28} className="mx-auto mb-2 opacity-40" />
                    No documents yet. Click "Seed Policies" to create sample documents.
                  </td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Web Sources tab */}
      {tab === 'web' && (
        <div className="space-y-4">
          {/* Add form */}
          <form onSubmit={handleAddSource} className="bg-white rounded-2xl shadow-card border border-gray-50 p-5">
            <h3 className="font-semibold text-ink-900 text-sm mb-4 flex items-center gap-2">
              <Globe size={16} className="text-brand-500" /> Add Website Source
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
              <input className="border border-gray-100 rounded-xl px-3 py-2.5 text-sm bg-surface focus:border-brand-400 outline-none transition-colors"
                placeholder="Website URL (https://...)" value={addUrl} onChange={e => setAddUrl(e.target.value)} />
              <input className="border border-gray-100 rounded-xl px-3 py-2.5 text-sm bg-surface focus:border-brand-400 outline-none transition-colors"
                placeholder="Source name" value={addName} onChange={e => setAddName(e.target.value)} />
              <select className="border border-gray-100 rounded-xl px-3 py-2.5 text-sm bg-surface focus:border-brand-400 outline-none transition-colors"
                value={addCat} onChange={e => setAddCat(e.target.value)}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g,' ')}</option>)}
              </select>
            </div>
            <button type="submit" disabled={adding}
              className="flex items-center gap-1.5 grad-blue text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50 shadow-md hover:opacity-90 transition-opacity">
              <Plus size={14} /> {adding ? 'Adding...' : 'Add Source'}
            </button>
          </form>

          {/* Sources list */}
          <div className="bg-white rounded-2xl shadow-card border border-gray-50 overflow-hidden">
            {webSources.length === 0 ? (
              <div className="text-center py-12 text-ink-300">
                <Globe size={28} className="mx-auto mb-2 opacity-40" />
                <div className="text-sm">No website sources yet. Add a URL above to index content.</div>
              </div>
            ) : (
              <table className="min-w-full text-sm">
                <thead><tr className="border-b border-gray-100">
                  {['Source','URL','Category','Status','Chunks','Last Synced','Actions'].map(h =>
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-ink-400 uppercase tracking-wider">{h}</th>)}
                </tr></thead>
                <tbody>
                  {webSources.map(s => (
                    <tr key={s.source_id} className="border-b border-gray-50 hover:bg-brand-50/30 transition-colors">
                      <td className="px-4 py-3 font-medium text-ink-900 text-sm max-w-xs truncate">{s.source_name}</td>
                      <td className="px-4 py-3 text-xs text-brand-500 max-w-xs truncate">
                        <a href={s.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                          className="hover:underline">{s.url}</a>
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-500">{s.category?.replace(/_/g,' ')}</td>
                      <td className="px-4 py-3"><TAG s={s.status} /></td>
                      <td className="px-4 py-3 text-ink-500">{s.chunks_created || '—'}</td>
                      <td className="px-4 py-3 text-xs text-ink-400">
                        {s.last_synced_at ? new Date(s.last_synced_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button onClick={() => ingestWebSource(s.source_id).then(loadAll)}
                            className="w-7 h-7 rounded-lg bg-brand-50 text-brand-500 hover:bg-brand-100 flex items-center justify-center transition-colors" title="Re-sync">
                            <RefreshCw size={13} />
                          </button>
                          <button onClick={() => deleteWebSource(s.source_id).then(loadAll)}
                            className="w-7 h-7 rounded-lg bg-gray-50 text-gray-400 hover:bg-rose-50 hover:text-rose-500 flex items-center justify-center transition-colors" title="Delete">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
