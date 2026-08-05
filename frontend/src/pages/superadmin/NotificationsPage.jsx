import { useState, useEffect, useCallback } from 'react'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import LoadingState from '../../components/superadmin/LoadingState.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

const PAGE_SIZE = 10

export default function NotificationsPage() {
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [offset, setOffset] = useState(0)
  const [filter, setFilter] = useState('all') // 'all' | 'unread'
  const [unreadCount, setUnreadCount] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.fetchNotifications({
        limit: PAGE_SIZE,
        offset,
        is_read: filter === 'unread' ? false : undefined,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }, [offset, filter])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const loadUnread = async () => {
      try {
        const res = await superadminApi.getUnreadNotificationCount()
        setUnreadCount(res?.count ?? 0)
      } catch {
        setUnreadCount(0)
      }
    }
    loadUnread()
  }, [])

  const markRead = async (notification) => {
    try {
      await superadminApi.markNotificationRead(notification.id)
      setRows((prev) => prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)))
      setUnreadCount((prev) => Math.max(0, prev - 1))
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to mark as read', 'error')
    }
  }

  const markAllRead = async () => {
    try {
      await superadminApi.markAllNotificationsRead()
      setRows((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
      addToast('All notifications marked as read')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to mark all as read', 'error')
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <AdminLayout title="Notifications" breadcrumb="Notifications">
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Notifications"
          subtitle={`${unreadCount} unread notification${unreadCount !== 1 ? 's' : ''}`}
          actions={
            <Button intent="secondary" onClick={markAllRead} disabled={unreadCount === 0}>
              Mark All Read
            </Button>
          }
        />

        <Card className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <button
              onClick={() => { setFilter('all'); setOffset(0) }}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-canvas)] text-[var(--color-ink-soft)] hover:bg-[var(--color-border)]'
              }`}
            >
              All
            </button>
            <button
              onClick={() => { setFilter('unread'); setOffset(0) }}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === 'unread'
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'bg-[var(--color-canvas)] text-[var(--color-ink-soft)] hover:bg-[var(--color-border)]'
              }`}
            >
              Unread
            </button>
          </div>

          {loading ? (
            <LoadingState rows={4} />
          ) : error ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-sm text-[var(--color-negative)]">{error}</p>
              <Button intent="secondary" onClick={load}>Try again</Button>
            </div>
          ) : rows.length === 0 ? (
            <EmptyState title="No notifications" description="You're all caught up." />
          ) : (
            <div className="flex flex-col">
              {rows.map((notification) => (
                <div
                  key={notification.id}
                  className={`flex items-start justify-between gap-3 border-b border-[var(--color-border)] px-4 py-4 last:border-0 ${
                    notification.is_read ? '' : 'bg-[var(--color-primary-soft)]'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {!notification.is_read && (
                        <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--color-primary)]" />
                      )}
                      <p className="text-sm font-medium text-[var(--color-ink)]">{notification.title || 'Notification'}</p>
                    </div>
                    {notification.message && (
                      <p className="mt-0.5 text-sm text-[var(--color-muted)]">{notification.message}</p>
                    )}
                    {notification.created_at && (
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {new Date(notification.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  {!notification.is_read && (
                    <button
                      onClick={() => markRead(notification)}
                      className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <span className="text-sm text-[var(--color-muted)]">Page {currentPage} of {totalPages}</span>
              <Button intent="secondary" size="sm" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          )}
        </Card>
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
