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
  const [readFilter, setReadFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState(new Set())

  const allVisibleSelected = items.length > 0 && items.every((item) => selectedIds.has(item.id))

  useEffect(() => {
    setSelectedIds(new Set())
  }, [offset, readFilter, typeFilter])

  const load = useCallback(async () => {
    try {
      const { data } = await apiClient.get('/notifications/', { params: { offset, limit: LIMIT, read: readFilter, type: typeFilter } })
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
  }, [offset, readFilter, typeFilter])

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
  const deleteNotification = async (item) => {
    try {
      await apiClient.delete(`/notifications/${item.id}/delete/`)
      setItems((current) => current.filter((row) => row.id !== item.id))
      setCount((current) => Math.max(0, current - 1))
      setUnread((current) => item.is_read ? current : Math.max(0, current - 1))
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError('Unable to delete notification.') }
  }
  const toggleSelected = (id) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const toggleSelectAll = () => {
    setSelectedIds(() => {
      if (allVisibleSelected) return new Set()
      return new Set(items.map((item) => item.id))
    })
  }
  const deleteSelected = async () => {
    const ids = [...selectedIds]
    if (!ids.length) return
    try {
      await apiClient.delete('/notifications/delete-bulk/', { data: { ids } })
      const selected = new Set(ids)
      const removed = items.filter((item) => selected.has(item.id))
      setItems((current) => current.filter((item) => !selected.has(item.id)))
      setCount((current) => Math.max(0, current - removed.length))
      setUnread((current) => Math.max(0, current - removed.filter((item) => !item.is_read).length))
      setSelectedIds(new Set())
      window.dispatchEvent(new Event('notifications-changed'))
      await load()
    } catch { setError('Unable to delete selected notifications.') }
  }
  const markSelected = async (isRead) => {
    const ids = [...selectedIds]
    if (!ids.length) return
    try {
      await apiClient.patch('/notifications/read-bulk/', { ids, is_read: isRead })
      setSelectedIds(new Set())
      await load()
      window.dispatchEvent(new Event('notifications-changed'))
    } catch { setError(`Unable to mark selected notifications as ${isRead ? 'read' : 'unread'}.`) }
  }

  return <ClientLayout><main className="mx-auto w-full max-w-5xl p-5">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-semibold text-[var(--color-ink)]">Notifications</h1><p className="text-sm text-[var(--color-muted)]">{unread} unread</p></div>
      <div className="flex gap-2">
        <label className="sr-only" htmlFor="notification-read-filter">Read status filter</label>
        <select id="notification-read-filter" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-[var(--color-ink)]" value={readFilter} onChange={(event) => { setReadFilter(event.target.value); setOffset(0) }}>
          <option value="all">All status</option>
          <option value="unread">Unread</option>
          <option value="read">Read</option>
        </select>
        <label className="sr-only" htmlFor="notification-type-filter">Notification type filter</label>
        <select id="notification-type-filter" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-[var(--color-ink)]" value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setOffset(0) }}>
          <option value="all">All types</option>
          <option value="manual">Manual</option>
          <option value="automated">Automated</option>
        </select>
        <button className="rounded-lg border border-[var(--color-primary)] px-4 py-2 text-[var(--color-primary)] disabled:opacity-50" disabled={!selectedIds.size} onClick={() => markSelected(true)}>Mark read{selectedIds.size ? ` (${selectedIds.size})` : ''}</button>
        <button className="rounded-lg border border-[var(--color-primary)] px-4 py-2 text-[var(--color-primary)] disabled:opacity-50" disabled={!selectedIds.size} onClick={() => markSelected(false)}>Mark unread{selectedIds.size ? ` (${selectedIds.size})` : ''}</button>
        <button className="rounded-lg border border-[var(--color-negative)] px-4 py-2 text-[var(--color-negative)] disabled:opacity-50" disabled={!selectedIds.size} onClick={deleteSelected}>Delete selected{selectedIds.size ? ` (${selectedIds.size})` : ''}</button>
      </div>
    </div>
    {error && <p role="alert" className="mb-4 text-sm text-red-600">{error}</p>}
    {!!items.length && <div className="mb-3 flex items-center gap-2 text-sm text-[var(--color-muted)]">
      <input type="checkbox" aria-label="Select all notifications on this page" checked={allVisibleSelected} onChange={toggleSelectAll} />
      <span>Select all on this page</span>
    </div>}
    <section aria-label="All notifications" className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      {loading ? <p className="p-5 text-[var(--color-muted)]">Loading notifications...</p> : !items.length && <p className="p-5 text-[var(--color-muted)]">No notifications.</p>}
      {items.map(item => <article key={item.id} className={`border-b border-[var(--color-border)] p-4 ${item.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}>
        <div className="flex items-start gap-3">
          <input type="checkbox" aria-label={`Select notification ${item.id}`} checked={selectedIds.has(item.id)} onChange={() => toggleSelected(item.id)} />
          <div className="min-w-0 flex-1"><div className="block whitespace-pre-wrap break-words text-[var(--color-ink)] select-text cursor-text">{item.message}</div>
        <div className="mt-2 text-sm text-[var(--color-muted)]">Type: {item.activity_type === 'manual' ? 'Manual' : item.activity_type === 'automated' ? 'Automated' : '—'}{item.activity_type === 'manual' && item.actor_name ? ` · User: ${item.actor_name}` : ''}</div>
        <div className="mt-2 flex items-center justify-between gap-2 text-sm text-[var(--color-muted)]"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time><div className="flex items-center gap-4">{item.link && <button type="button" className="text-[var(--color-primary)]" onClick={() => openNotification(item)}>Open</button>}<button className="text-[var(--color-primary)]" onClick={() => updateRead(item, !item.is_read)}>{item.is_read ? 'Mark unread' : 'Mark read'}</button><button type="button" aria-label="Delete notification" title="Delete notification" className="text-[var(--color-negative)]" onClick={() => deleteNotification(item)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4"><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg></button></div></div></div></div>
      </article>)}
      <div className="flex items-center justify-between p-4 text-sm text-[var(--color-muted)]"><button disabled={offset === 0} className="disabled:opacity-40" onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + LIMIT, count)} of ${count}` : '0'}</span><button disabled={offset + LIMIT >= count} className="disabled:opacity-40" onClick={() => setOffset(offset + LIMIT)}>Next</button></div>
    </section>
  </main></ClientLayout>
}
