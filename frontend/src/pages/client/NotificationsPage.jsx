import { useCallback, useEffect, useRef, useState } from 'react'
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
  const [undoItems, setUndoItems] = useState([])
  const deleteTimers = useRef(new Map())

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

  useEffect(() => () => {
    deleteTimers.current.forEach((timer) => window.clearTimeout(timer))
    deleteTimers.current.clear()
  }, [])
  useEffect(() => { load() }, [load])
  const updateRead = async (item, isRead) => {
    try {
      await apiClient.patch(`/notifications/${item.id}/`, { is_read: isRead })
      await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to update notification.') }
  }
  const openNotification = async (item) => {
    if (!item.link) return
    if (!item.is_read) await updateRead(item, true)
    navigate(item.link)
  }
  const markAll = async () => {
    try {
      await apiClient.post('/notifications/read-all/')
      setOffset(0)
      if (offset === 0) await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to mark notifications as read.') }
  }
  const deleteNotification = async (item) => {
    try {
      await apiClient.delete(`/notifications/${item.id}/delete/`)
      setItems((current) => current.filter((row) => row.id !== item.id))
      setCount((current) => Math.max(0, current - 1))
      setUnread((current) => item.is_read ? current : Math.max(0, current - 1))
      setUndoItems((current) => [...current.filter((row) => row.id !== item.id), item])
      const timer = window.setTimeout(async () => {
        deleteTimers.current.delete(item.id)
        setUndoItems((current) => current.filter((row) => row.id !== item.id))
        try { await apiClient.delete(`/notifications/${item.id}/delete/?permanent=true`) } catch { /* backend cleanup is authoritative */ }
      }, 10000)
      deleteTimers.current.set(item.id, timer)
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to delete notification.') }
  }
  const undoDelete = async (item) => {
    const timer = deleteTimers.current.get(item.id)
    if (timer) window.clearTimeout(timer)
    deleteTimers.current.delete(item.id)
    try {
      await apiClient.post(`/notifications/${item.id}/restore/`)
      setUndoItems((current) => current.filter((row) => row.id !== item.id))
      setOffset(0)
      await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Undo window has expired.') }
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
    {!!undoItems.length && <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--color-primary)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm text-[var(--color-ink)]">
      <span>{undoItems.length === 1 ? 'Notification deleted.' : `${undoItems.length} notifications deleted.`} Undo is available for 10 seconds.</span>
      <div className="flex flex-wrap gap-2">{undoItems.map(item => <button key={item.id} type="button" className="text-[var(--color-primary)]" onClick={() => undoDelete(item)}>Undo</button>)}</div>
    </div>}
    <section aria-label="All notifications" className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      {loading ? <p className="p-5 text-[var(--color-muted)]">Loading notifications...</p> : !items.length && <p className="p-5 text-[var(--color-muted)]">No notifications.</p>}
      {items.map(item => <article key={item.id} className={`border-b border-[var(--color-border)] p-4 ${item.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}>
        <div className="block whitespace-pre-wrap break-words text-[var(--color-ink)] select-text cursor-text">{item.message}</div>
        <div className="mt-2 text-sm text-[var(--color-muted)]">Type: {item.activity_type === 'manual' ? 'Manual' : item.activity_type === 'automated' ? 'Automated' : '—'}{item.activity_type === 'manual' && item.actor_name ? ` · User: ${item.actor_name}` : ''}</div>
        <div className="mt-2 flex items-center justify-between gap-2 text-sm text-[var(--color-muted)]"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time><div className="flex items-center gap-4">{item.link && <button type="button" className="text-[var(--color-primary)]" onClick={() => openNotification(item)}>Open</button>}<button className="text-[var(--color-primary)]" onClick={() => updateRead(item, !item.is_read)}>{item.is_read ? 'Mark unread' : 'Mark read'}</button><button type="button" aria-label="Delete notification" title="Delete notification" className="text-[var(--color-negative)]" onClick={() => deleteNotification(item)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg></button></div></div>
      </article>)}
      <div className="flex items-center justify-between p-4 text-sm text-[var(--color-muted)]"><button disabled={offset === 0} className="disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + LIMIT, count)} of ${count}` : '0'}</span><button disabled={offset + LIMIT >= count} className="disabled:opacity-40" onClick={() => setOffset(offset + LIMIT)}>Next</button></div>
    </section>
  </main></ClientLayout>
}
