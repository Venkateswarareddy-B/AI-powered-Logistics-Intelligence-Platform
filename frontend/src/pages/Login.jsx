import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('demo_admin')
  const [password, setPassword] = useState('Demo@YottaFlex2026')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await signIn(username, password)
      navigate('/')
    } catch {
      setError('Invalid credentials. Try demo_admin / Demo@YottaFlex2026')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen sidebar-gradient flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md p-8 md:p-10 animate-fade-in-up">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl grad-blue flex items-center justify-center mx-auto mb-4 shadow-lg shadow-brand-500/30">
            <span className="text-white font-bold text-2xl">YF</span>
          </div>
          <h1 className="text-2xl font-bold text-ink-900">YottaFlex</h1>
          <p className="text-ink-500 text-sm mt-1">AI-Powered Logistics Intelligence Platform</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Username</label>
            <input
              className="w-full bg-surface border border-gray-100 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 outline-none transition-all"
              value={username} onChange={e => setUsername(e.target.value)}
              placeholder="demo_admin" required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1.5">Password</label>
            <input
              type="password"
              className="w-full bg-surface border border-gray-100 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 outline-none transition-all"
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••••" required
            />
          </div>
          {error && <div className="text-rose-500 text-sm bg-rose-50 px-3 py-2 rounded-lg">{error}</div>}
          <button
            type="submit"
            disabled={loading}
            className="w-full grad-blue text-white font-semibold py-3 rounded-xl transition-all hover:shadow-lg hover:shadow-brand-500/30 disabled:opacity-60"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="mt-6 p-4 bg-brand-50 rounded-xl text-xs text-brand-700 border border-brand-100/60">
          <div className="font-semibold mb-1.5 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500"></span> Demo Credentials
          </div>
          <div>Username: <strong>demo_admin</strong></div>
          <div>Password: <strong>Demo@YottaFlex2026</strong></div>
          <div className="mt-1.5 text-brand-500/70">These are demo-only credentials.</div>
        </div>
      </div>
    </div>
  )
}
