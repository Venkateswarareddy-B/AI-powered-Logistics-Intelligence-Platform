import React, { useState, useRef, useEffect } from 'react'
import PageHeader from '../components/PageHeader'
import { useAuth } from '../context/AuthContext'
import api from '../services/api'
import { Send } from 'lucide-react'

const SUGGESTIONS = [
  "Which shipments are likely delayed today?",
  "Which carriers have the worst performance?",
  "Summarize current logistics situation",
  "Which facilities are most congested?",
]

export default function AIAssistant() {
  const [messages, setMessages] = useState([{
    role: 'assistant',
    content: 'Hello! I\'m the YottaFlex AI assistant. I can answer questions about your logistics operations. Ask me anything about shipments, carriers, delays, or SLA status.',
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const { user } = useAuth()
  const messagesEndRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async (text) => {
    const msg = text || input
    if (!msg.trim()) return
    setInput('')
    setMessages(m => [...m, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const r = await api.post('/api/assistant/chat', { message: msg })
      setMessages(m => [...m, { role: 'assistant', content: r.data.response || r.data.message }])
    } catch (e) {
      const status = e.response?.status
      if (status === 404 || status === 503) {
        setMessages(m => [...m, {
          role: 'assistant',
          content: '⚙️ The GenAI assistant requires a Groq API key (Phase 16). Set GROQ_API_KEY and GROQ_ENABLED=true in your .env file to enable this feature.',
        }])
      } else {
        setMessages(m => [...m, { role: 'assistant', content: 'Sorry, an error occurred. Please try again.' }])
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-8rem)]">
      <PageHeader title="AI Assistant" subtitle="Powered by Groq + Llama (requires GROQ_API_KEY)" />
      <div className="flex gap-2 mb-4 flex-wrap">
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => send(s)}
            className="text-xs border border-brand-200 text-brand-600 px-3 py-1 rounded-full hover:bg-brand-50 transition-colors">
            {s}
          </button>
        ))}
      </div>
      <div className="flex-1 bg-white rounded-xl border shadow-sm p-4 overflow-y-auto space-y-4 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
              m.role === 'user' ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-800'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-xl px-4 py-3 text-sm text-gray-500">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="flex gap-2 mt-3">
        <input
          className="flex-1 border rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask about shipments, delays, carriers..."
        />
        <button onClick={() => send()} disabled={loading || !input.trim()}
          className="bg-brand-600 text-white px-4 py-2.5 rounded-xl hover:bg-brand-500 disabled:opacity-50">
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}
