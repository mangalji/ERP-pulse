import { useState, useCallback, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { clientApi } from '../../services/client.js'

const TYPE_TONE = {
  INFO: 'neutral',
  SUCCESS: 'positive',
  WARNING: 'netsuite',
  ERROR: 'negative',
  SYSTEM: 'primary',
}

export default function NotificationsPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [notifications, setNotifications] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [offset, setOffset] = useState(0)
  const limit = 20

  const loadNotifications = useCallback(async (selectedOffset) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit, offset: selectedOffset }
      if (filter === 'unread') params.is_read = false
      const res = await clientApi.fetchNotifications(params)
      const list = res?.results ?? res ?? []
      setNotifications(list)
      setCount(res?.count ?? list.length)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    loadNotifications(0)
    setOffset(0)
  }, [loadNotifications, filter])

  const handleMarkRead = async (id) => {
    try {
      await clientApi.markNotificationRead(id)
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to mark as read', 'error')
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await clientApi.markAllNotificationsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      addToast('All notifications marked as read', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to mark all as read', 'error')
    }
  }

  const unread = notifications.filter((n) => !n.is_read).length

  return (
    <ClientLayout title="Notifications" breadcrumb="Notifications">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Notifications
            </h1>
            <p className="text-sm text-[var(--color-muted)]">
              {unread > 0 ? `You have ${unread} unread notification${unread > 1 ? 's' : ''}.` : 'You are all caught up.'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1 rounded-lg border border-[var(--color-border)] p-1">
              {['all', 'unread'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                    filter === f
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'text-[var(--color-muted)] hover:text-[var(--color-ink)]'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
            <Button intent="secondary" size="sm" onClick={handleMarkAllRead}>
              Mark all read
            </Button>
          </div>
        </div>

        <Card className="p-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={() => loadNotifications(offset)} />
          ) : notifications.length === 0 ? (
            <EmptyState
              title="No notifications"
              description={filter === 'unread' ? 'You have no unread notifications.' : 'Notifications will appear here.'}
            />
          ) : (
            <div className="flex flex-col gap-2">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className={`flex items-start justify-between gap-3 rounded-lg border border-[var(--color-border)] px-4 py-3 ${
                    n.is_read ? '' : 'bg-[var(--color-primary-soft)]'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge tone={TYPE_TONE[n.type] || 'neutral'}>{n.type || 'INFO'}</Badge>
                      {!n.is_read && (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--color-primary)]" />
                      )}
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">{n.title}</p>
                    </div>
                    {n.message && <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{n.message}</p>}
                    <p className="mt-1 text-xs text-[var(--color-muted)]">{new Date(n.created_at).toLocaleString()}</p>
                  </div>
                  {!n.is_read && (
                    <Button size="sm" intent="ghost" onClick={() => handleMarkRead(n.id)}>
                      Mark read
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {count > limit && (
          <div className="flex items-center justify-center gap-3">
            <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => {
              const next = Math.max(0, offset - limit)
              setOffset(next)
              loadNotifications(next)
            }}>
              Previous
            </Button>
            <span className="text-xs text-[var(--color-muted)]">
              {offset + 1}–{Math.min(offset + limit, count)} of {count}
            </span>
            <Button
              intent="secondary"
              size="sm"
              disabled={offset + limit >= count}
              onClick={() => {
                const next = offset + limit
                setOffset(next)
                loadNotifications(next)
              }}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </ClientLayout>
  )
}
