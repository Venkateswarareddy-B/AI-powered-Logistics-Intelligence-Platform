import React, { useState, useRef, useEffect } from 'react'
import { runAgent, searchRag } from '../services/api'
import { Send, Bot, CheckCircle, XCircle, AlertCircle, Trash2, Copy, ChevronDown, ChevronUp, Zap } from 'lucide-react'

const SUGGESTIONS = [
  { text: "Analyze shipment delays", icon: "🔍" },
  { text: "Find high-risk shipments", icon: "⚠️" },
  { text: "Check carrier performance", icon: "🚛" },
  { text: "Explain SLA breaches", icon: "📊" },
  { text: "Search logistics knowledge", icon: "📚" },
  { text: "Generate operations summary", icon: "📋" },
]

const TypingDots = () => (
  <div className="flex gap-1 items-center py-1">
    {[0,1,2].map(i => (
      <div key={i} className="w-2 h-2 rounded-full bg-brand-400 animate-bounce"
        style={{ animationDelay: `${i*0.15}s` }} />
    ))}
  </div>
)

const ToolChip = ({ tool, success }) => (
  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full mr-1 mb-1 ${
    success ? 'bg-emerald-50 text-emerald-600 border border-emerald-100'
             : 'bg-rose-50 text-rose-500 border border-rose-100'}`}>
    {success ? <CheckCircle size={10} /> : <XCircle size={10} />}
    {tool}
  </span>
)

const AssistantMessage = ({ msg }) => {
  const [showSources, setShowSources] = useState(false)
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(msg.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex gap-3 animate-fade-in-up">
      <div className="w-8 h-8 rounded-xl grad-blue flex items-center justify-center shrink-0 shadow-md mt-0.5">
        <Bot size={16} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white rounded-2xl rounded-tl-sm shadow-card border border-gray-100 px-4 py-3">
          <p className="text-sm text-ink-800 whitespace-pre-wrap leading-relaxed">{msg.content}</p>

          {/* Tools used */}
          {msg.tools?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs font-semibold text-ink-400 mb-1.5 flex items-center gap-1">
                <Zap size={11} /> Tools used
              </div>
              <div>{msg.tools.map((t,i) => <ToolChip key={i} tool={t.tool} success={t.success} />)}</div>
            </div>
          )}

          {/* Confidence */}
          {msg.confidence && (
            <div className="mt-1.5 flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${
                msg.confidence === 'high' ? 'bg-emerald-500' :
                msg.confidence === 'medium' ? 'bg-amber-500' : 'bg-rose-500'}`} />
              <span className="text-xs text-ink-400">Confidence: {msg.confidence}</span>
            </div>
          )}

          {/* Approval required */}
          {msg.approvalRequired && (
            <div className="mt-2 text-xs text-amber-600 bg-amber-50 rounded-lg px-2.5 py-1.5 flex items-center gap-1">
              <AlertCircle size={11} /> Approval required for this action
            </div>
          )}

          {/* Policy sources */}
          {msg.policySources?.length > 0 && (
            <div className="mt-2">
              <button onClick={() => setShowSources(s => !s)}
                className="text-xs text-brand-500 flex items-center gap-1 hover:text-brand-600 transition-colors">
                {showSources ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                {msg.policySources.length} policy source{msg.policySources.length > 1 ? 's' : ''}
              </button>
              {showSources && (
                <div className="mt-1.5 space-y-1.5">
                  {msg.policySources.map((p, i) => (
                    <div key={i} className="bg-brand-50 rounded-lg px-3 py-2 text-xs border border-brand-100">
                      <div className="font-semibold text-brand-700">{p.document}</div>
                      <div className="text-ink-500">{p.category}</div>
                      {p.excerpt && <div className="text-ink-400 mt-1 line-clamp-2">{p.excerpt}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 mt-1 ml-1">
          <button onClick={copy} className="text-xs text-ink-400 hover:text-ink-600 flex items-center gap-1 transition-colors">
            <Copy size={11} /> {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Agent() {
  const [messages, setMessages] = useState([{ role: 'welcome' }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async (text) => {
    const msg = text || input
    if (!msg.trim()) return
    setInput('')
    setMessages(m => [...m, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const r = await runAgent(msg)
      setMessages(m => [...m, {
        role: 'assistant',
        content: r.data.recommendation || r.data.findings || 'No recommendation generated.',
        tools: r.data.tools_used || [],
        confidence: r.data.confidence,
        policySources: r.data.supporting_policy_sources || [],
        approvalRequired: r.data.approval_required,
        decisionId: r.data.agent_decision_id,
      }])
    } catch (e) {
      setMessages(m => [...m, {
        role: 'assistant',
        content: 'Sorry, the agent encountered an error: ' + (e.response?.data?.detail || e.message || 'Unknown error'),
        tools: [],
      }])
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const clear = () => { setMessages([{ role: 'welcome' }]); setInput('') }

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Logistics Agent</h1>
          <p className="text-xs text-ink-500 mt-0.5">Tool-calling AI with live data access</p>
        </div>
        {messages.length > 1 && (
          <button onClick={clear} className="flex items-center gap-1.5 text-xs text-ink-400 hover:text-rose-500 border border-gray-200 rounded-xl px-3 py-2 transition-colors hover:border-rose-200">
            <Trash2 size={13} /> Clear
          </button>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-4 min-h-0 pr-1">
        {messages.map((m, i) => {
          if (m.role === 'welcome') return (
            <div key={i} className="text-center py-8 animate-fade-in-up">
              <div className="w-14 h-14 rounded-2xl grad-blue flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Bot size={26} className="text-white" />
              </div>
              <h2 className="text-lg font-bold text-ink-900 mb-1">Hello! I'm YottaFlex Logistics AI</h2>
              <p className="text-sm text-ink-500 max-w-md mx-auto mb-6">
                I can help you track shipments, analyze delays, understand SLA performance, and answer logistics questions using your operational data and knowledge base.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-w-lg mx-auto">
                {SUGGESTIONS.map(s => (
                  <button key={s.text} onClick={() => send(s.text)}
                    className="bg-white text-left rounded-xl px-3 py-2.5 text-xs text-ink-700 border border-gray-100 shadow-soft hover:border-brand-200 hover:bg-brand-50 transition-all hover:-translate-y-0.5">
                    <span className="mr-1.5">{s.icon}</span>{s.text}
                  </button>
                ))}
              </div>
            </div>
          )
          if (m.role === 'user') return (
            <div key={i} className="flex justify-end animate-fade-in-up">
              <div className="max-w-[75%] bg-brand-500 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm shadow-md">
                {m.content}
              </div>
            </div>
          )
          return <AssistantMessage key={i} msg={m} />
        })}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-xl grad-blue flex items-center justify-center shrink-0 shadow-md">
              <Bot size={16} className="text-white" />
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm shadow-card border border-gray-100 px-4 py-3">
              <TypingDots />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="mt-3 shrink-0">
        <div className="flex gap-2 bg-white rounded-2xl border border-gray-200 shadow-soft p-1.5 focus-within:border-brand-400 focus-within:shadow-card transition-all">
          <input
            ref={inputRef}
            className="flex-1 bg-transparent text-sm outline-none px-3 py-2 text-ink-800 placeholder:text-ink-300"
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && !loading && send()}
            placeholder="Ask about shipments, delays, carriers, SLA performance..."
          />
          <button onClick={() => send()} disabled={loading || !input.trim()}
            className="grad-blue text-white px-4 py-2 rounded-xl hover:opacity-90 disabled:opacity-40 transition-opacity shrink-0">
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
