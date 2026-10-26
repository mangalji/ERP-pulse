import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'

export default function NotificationMenu({ userId }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [unread, setUnread] = useState(0)
  const [onlyUnread, setOnlyUnread] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const ref = useRef(null)
  const navigate = useNavigate()
  const limit = showAll ? 20 : 8

  const load = useCallback(async () => {
    if (!userId) return
    try {
      const { data } = await apiClient.get('/notifications/', { params: { offset, limit, unread: onlyUnread } })
      setItems(data.results); setCount(data.count); setUnread(data.unread_count); setError('')
    } catch {
      setError('Unable to load notifications.')
    }
  }, [userId, offset, limit, onlyUnread])

  useEffect(() => { load(); const timer = window.setInterval(load, 30000); return () => window.clearInterval(timer) }, [load])
  useEffect(() => {
    const close = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])
  const setRead = async (item, value) => {
    try { await apiClient.patch(`/notifications/${item.id}/`, { is_read: value }); await load() }
    catch { setError('Unable to update notification.') }
  }
  const markAll = async () => {
    try { await apiClient.post('/notifications/read-all/'); setOffset(0); await load() }
    catch { setError('Unable to mark notifications as read.') }
  }

  return <div className="relative" ref={ref}>
    <button type="button" aria-label={`Notifications, ${unread} unread`} aria-expanded={open} onClick={() => setOpen(!open)} className="relative flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--color-border)] text-[var(--color-ink)]">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5"><path strokeLinecap="round" strokeLinejoin="round" d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" /></svg>
      {unread > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1.5 text-xs font-bold text-white">{unread > 99 ? '99+' : unread}</span>}
    </button>
    {open && <section aria-label="Notifications" className="absolute right-0 z-[190] mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] p-3 text-sm">
        <strong>Notifications</strong>
        <button type="button" className="text-[var(--color-primary)]" onClick={() => { setShowAll(!showAll); setOffset(0) }}>{showAll ? 'Recent' : 'Show all'}</button>
        <button type="button" className="text-[var(--color-primary)]" onClick={() => { setOnlyUnread(!onlyUnread); setOffset(0) }}>{onlyUnread ? 'All' : 'Unread'}</button>
        <button type="button" disabled={!unread} className="text-[var(--color-primary)] disabled:opacity-50" onClick={markAll}>Mark all read</button>
      </div>
      {error && <p role="alert" className="px-3 py-2 text-sm text-red-600">{error}</p>}
      <div className="max-h-96 overflow-y-auto">
        {!items.length && <p className="p-4 text-sm text-[var(--color-muted)]">No notifications.</p>}
        {items.map(item => <div key={item.id} className={`border-b border-[var(--color-border)] p-3 text-sm ${item.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}>
          <button type="button" className="block w-full text-left text-[var(--color-ink)]" onClick={async () => { if (!item.is_read) await setRead(item, true); if (item.link) { setOpen(false); navigate(item.link) } }}>{item.message}</button>
          {showAll && <div className="mt-1 text-xs text-[var(--color-muted)]">Type: {item.activity_type === 'manual' ? 'Manual' : item.activity_type === 'automated' ? 'Automated' : '—'}{item.activity_type === 'manual' && item.actor_name ? ` · User: ${item.actor_name}` : ''}</div>}
          <div className="mt-1 flex items-center justify-between gap-2 text-xs text-[var(--color-muted)]"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time><button type="button" className="text-[var(--color-primary)]" onClick={() => setRead(item, !item.is_read)}>{item.is_read ? 'Mark unread' : 'Mark read'}</button></div>
        </div>)}
      </div>
      {showAll && <div className="flex justify-between p-3 text-xs"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + limit, count)} of ${count}` : '0'}</span><button disabled={offset + limit >= count} onClick={() => setOffset(offset + limit)}>Next</button></div>}
    </section>}
  </div>
}
