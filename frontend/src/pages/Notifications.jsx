import React, { useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'
import { getNotifications, getNotifStats, markNotifRead, markAllNotifRead } from '../services/api'
import { Bell, CheckCheck, Mail, MailOpen } from 'lucide-react'

export default function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [stats, setStats] = useState({ total: 0, unread: 0, read: 0 })
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  const load = async () => {
    setLoading(true)
    try {
      const [notifR, statsR] = await Promise.all([
        getNotifications(filter === 'unread'),
        getNotifStats(),
      ])
      setNotifications(notifR.data)
      setStats(statsR.data)
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [filter])

  const markRead = async (id) => {
    await markNotifRead(id)
    load()
  }

  const markAll = async () => {
    await markAllNotifRead()
    load()
  }

  return (
    <div>
      <PageHeader title="Notifications" subtitle={`${stats.unread || 0} unread of ${stats.total || 0} total`}>
        <button onClick={markAll} disabled={!stats.unread}
          className="flex items-center gap-1 text-sm border rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50">
          <CheckCheck size={14} /> Mark all read
        </button>
      </PageHeader>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-4">
        <button onClick={() => setFilter('all')}
          className={`px-3 py-1.5 rounded-lg text-sm ${filter === 'all' ? 'bg-brand-600 text-white' : 'border hover:bg-gray-50'}`}>
          All ({stats.total || 0})
        </button>
        <button onClick={() => setFilter('unread')}
          className={`px-3 py-1.5 rounded-lg text-sm ${filter === 'unread' ? 'bg-brand-600 text-white' : 'border hover:bg-gray-50'}`}>
          Unread ({stats.unread || 0})
        </button>
      </div>

      {/* Notification list */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? <LoadingSpinner /> : notifications.length === 0 ? (
          <div className="text-center py-10 text-gray-400">
            <Bell size={32} className="mx-auto mb-2 opacity-50" />
            <div>No notifications</div>
          </div>
        ) : (
          <div className="divide-y">
            {notifications.map(n => (
              <div key={n.notification_id} className={`p-4 hover:bg-gray-50 ${!n.is_read ? 'bg-blue-50/50' : ''}`}>
                <div className="flex items-start gap-3">
                  {!n.is_read ? (
                    <Mail size={18} className="text-blue-500 mt-0.5 shrink-0" />
                  ) : (
                    <MailOpen size={18} className="text-gray-400 mt-0.5 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-medium text-sm text-gray-800">{n.title}</span>
                      <StatusBadge value={n.severity === 'CRITICAL' ? 'BREACHED' : n.severity === 'HIGH' ? 'AT_RISK' : 'ON_TIME'} />
                    </div>
                    {n.body && <div className="text-xs text-gray-500">{n.body}</div>}
                    <div className="text-xs text-gray-400 mt-1">
                      {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                      {n.shipment_id && ` · ${n.shipment_id}`}
                    </div>
                  </div>
                  {!n.is_read && (
                    <button onClick={() => markRead(n.notification_id)}
                      className="text-xs text-brand-600 hover:text-brand-800 shrink-0">
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
