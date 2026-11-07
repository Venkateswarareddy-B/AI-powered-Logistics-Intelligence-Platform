import React, { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  LayoutDashboard, Package, TrendingUp, AlertTriangle, Truck, Building2,
  Route, Bot, BookOpen, Brain, FileBarChart, Bell, History, Server,
  Users, Settings, LogOut, Menu, X, Search, ChevronDown
} from 'lucide-react'

const NAV = [
  { to: '/',              icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/shipments',     icon: Package,         label: 'Shipments' },
  { to: '/eta',           icon: TrendingUp,      label: 'ETA Prediction' },
  { to: '/alerts',        icon: AlertTriangle,   label: 'Delay Alerts' },
  { to: '/carriers',      icon: Truck,           label: 'Carriers' },
  { to: '/facilities',    icon: Building2,       label: 'Facilities' },
  { to: '/routes',        icon: Route,           label: 'Routes' },
  { to: '/ai-assistant',  icon: Bot,             label: 'AI Assistant' },
  { to: '/knowledge',     icon: BookOpen,        label: 'Knowledge Base' },
  { to: '/agent',         icon: Brain,           label: 'Agent' },
  { to: '/reports',       icon: FileBarChart,    label: 'Reports' },
  { to: '/notifications', icon: Bell,            label: 'Notifications' },
  { to: '/audit',         icon: History,         label: 'Audit History' },
  { to: '/system',        icon: Server,          label: 'System Health' },
  { to: '/users',         icon: Users,           label: 'Users' },
  { to: '/settings',      icon: Settings,        label: 'Settings' },
]

export default function Layout({ children }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  const currentPage = NAV.find(n =>
    n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to)
  )?.label || 'Dashboard'

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Desktop Sidebar */}
      <aside className={`${open ? 'w-60' : 'w-16'} sidebar-gradient flex flex-col transition-all duration-300 shrink-0 hidden md:flex`}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-white/5">
          <div className="w-9 h-9 rounded-xl grad-blue flex items-center justify-center shrink-0 shadow-lg shadow-brand-500/30">
            <span className="text-white font-bold text-sm">YF</span>
          </div>
          {open && (
            <div className="overflow-hidden">
              <div className="text-white font-bold text-base leading-tight tracking-tight">YottaFlex</div>
              <div className="text-brand-50/60 text-xs leading-tight">Logistics AI</div>
            </div>
          )}
          <button onClick={() => setOpen(o => !o)}
            className="ml-auto text-white/40 hover:text-white transition-colors">
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto scrollbar-thin py-3 px-2 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${
                  isActive
                    ? 'nav-active text-white font-semibold'
                    : 'text-white/50 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              {open && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="border-t border-white/5 p-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full grad-blue flex items-center justify-center shrink-0 shadow-md">
              <span className="text-white text-xs font-bold">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            {open && (
              <div className="flex-1 min-w-0">
                <div className="text-white text-xs font-medium truncate">{user?.username}</div>
                <div className="text-white/40 text-xs">{user?.role}</div>
              </div>
            )}
            <button onClick={() => { signOut(); navigate('/login') }}
              className="text-white/40 hover:text-rose-500 transition-colors shrink-0">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-60 sidebar-gradient flex flex-col animate-slide-in">
            <div className="flex items-center gap-3 px-4 py-5 border-b border-white/5">
              <div className="w-9 h-9 rounded-xl grad-blue flex items-center justify-center">
                <span className="text-white font-bold text-sm">YF</span>
              </div>
              <div>
                <div className="text-white font-bold text-base">YottaFlex</div>
                <div className="text-brand-50/60 text-xs">Logistics AI</div>
              </div>
              <button onClick={() => setMobileOpen(false)} className="ml-auto text-white/60">
                <X size={18} />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto scrollbar-thin py-3 px-2">
              {NAV.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                      isActive ? 'nav-active text-white font-semibold' : 'text-white/50 hover:text-white hover:bg-white/5'
                    }`
                  }
                >
                  <Icon size={18} className="shrink-0" />
                  <span className="truncate">{label}</span>
                </NavLink>
              ))}
            </nav>
          </aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white/80 glass border-b border-gray-100 px-4 md:px-6 py-3.5 flex items-center justify-between shrink-0 z-20">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="md:hidden text-ink-700">
              <Menu size={20} />
            </button>
            <div>
              <h2 className="text-base font-bold text-ink-900">{currentPage}</h2>
              <p className="text-xs text-ink-500 hidden sm:block">
                Welcome back, {user?.username || 'User'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            {/* Search (desktop) */}
            <div className="hidden md:flex items-center gap-2 bg-surface border border-gray-100 rounded-xl px-3 py-2 w-56">
              <Search size={15} className="text-ink-300" />
              <input className="bg-transparent text-sm outline-none flex-1 text-ink-700 placeholder:text-ink-300"
                placeholder="Search..." />
            </div>

            {/* Notifications */}
            <button onClick={() => navigate('/notifications')}
              className="relative w-9 h-9 rounded-xl bg-surface border border-gray-100 flex items-center justify-center hover:bg-brand-50 transition-colors">
              <Bell size={17} className="text-ink-500" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full"></span>
            </button>

            {/* Profile */}
            <div className="relative">
              <button onClick={() => setProfileOpen(o => !o)}
                className="flex items-center gap-2 hover:bg-surface rounded-xl px-2 py-1.5 transition-colors">
                <div className="w-8 h-8 rounded-lg grad-blue flex items-center justify-center shadow-md">
                  <span className="text-white text-xs font-bold">
                    {user?.username?.[0]?.toUpperCase() || 'U'}
                  </span>
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-xs font-semibold text-ink-900">{user?.username}</div>
                  <div className="text-xs text-ink-500">{user?.role}</div>
                </div>
                <ChevronDown size={14} className="text-ink-300 hidden sm:block" />
              </button>
              {profileOpen && (
                <div className="absolute right-0 top-12 bg-white rounded-xl shadow-card border border-gray-100 py-1 w-44 z-50">
                  <button onClick={() => { navigate('/settings'); setProfileOpen(false) }}
                    className="w-full text-left px-3 py-2 text-sm text-ink-700 hover:bg-surface transition-colors">
                    Settings
                  </button>
                  <button onClick={() => { signOut(); navigate('/login') }}
                    className="w-full text-left px-3 py-2 text-sm text-rose-500 hover:bg-rose-50 transition-colors">
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
