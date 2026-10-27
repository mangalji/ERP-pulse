import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import apiClient from '../../services/apiClient.js'

const LIMIT = 15

export default function NotificationsPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [unread, setUnread] = useState(0)
  const [offset, setOffset] = useState(0)
  const [onlyUnread, setOnlyUnread] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get('/notifications/', { params: { offset, limit: LIMIT, unread: onlyUnread } })
      if (offset > 0 && data.count <= offset) {
        setOffset(Math.max(0, Math.ceil(data.count / LIMIT) - 1) * LIMIT)
        return
      }
      setItems(data.results || [])
      setCount(data.count || 0)
      setUnread(data.unread_count || 0)
      setError('')
    } catch {
      setError('Unable to load notifications.')
    } finally {
      setLoading(false)
    }
  }, [offset, onlyUnread])

  useEffect(() => { load() }, [load])
  const updateRead = async (item, isRead) => {
    try {
      await apiClient.patch(`/notifications/${item.id}/`, { is_read: isRead })
      await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to update notification.') }
  }
  const markAll = async () => {
    try {
      await apiClient.post('/notifications/read-all/')
      setOffset(0)
      if (offset === 0) await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to mark notifications as read.') }
  }

  return <ClientLayout><main className="mx-auto w-full max-w-5xl p-5">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold text-[var(--color-ink)]">Notifications</h1><p className="text-sm text-[var(--color-muted)]">{unread} unread</p></div>
      <div className="flex gap-2">
        <button className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-[var(--color-ink)]" onClick={() => { setOnlyUnread(!onlyUnread); setOffset(0) }}>{onlyUnread ? 'Show all' : 'Unread only'}</button>
        <button className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-[var(--color-ink)] disabled:opacity-50" disabled={!unread} onClick={markAll}>Mark all read</button>
      </div>
    </div>
    {error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}
    <section aria-label="All notifications" className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      {loading ? <p className="p-5 text-[var(--color-muted)]">Loading notifications...</p> : !items.length && <p className="p-5 text-[var(--color-muted)]">No notifications.</p>}
      {items.map(item => <article key={item.id} className={`border-b border-[var(--color-border)] p-4 ${item.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}>
        <button className="block w-full text-left text-[var(--color-ink)]" onClick={async () => { if (!item.is_read) await updateRead(item, true); if (item.link) navigate(item.link) }}>{item.message}</button>
        <div className="mt-2 text-sm text-[var(--color-muted)]">Type: {item.activity_type === 'manual' ? 'Manual' : item.activity_type === 'automated' ? 'Automated' : '—'}{item.activity_type === 'manual' && item.actor_name ? ` · User: ${item.actor_name}` : ''}</div>
        <div className="mt-2 flex items-center justify-between gap-2 text-sm text-[var(--color-muted)]"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time><button className="text-[var(--color-primary)]" onClick={() => updateRead(item, !item.is_read)}>{item.is_read ? 'Mark unread' : 'Mark read'}</button></div>
      </article>)}
      <div className="flex items-center justify-between p-4 text-sm text-[var(--color-muted)]"><button disabled={offset === 0} className="disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + LIMIT, count)} of ${count}` : '0'}</span><button disabled={offset + LIMIT >= count} className="disabled:opacity-40" onClick={() => setOffset(offset + LIMIT)}>Next</button></div>
    </section>
  </main></ClientLayout>
}
