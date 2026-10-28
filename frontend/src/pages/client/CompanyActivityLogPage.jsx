import { useCallback, useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import apiClient from '../../services/apiClient.js'

const PAGE_SIZE = 15
const titleCase = (value) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export default function CompanyActivityLogPage() {
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState({ module: '', status: '', activity_type: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await apiClient.get('/audit/events/', { params: { offset, limit: PAGE_SIZE, ...filters } })
      if (offset && data.count <= offset) {
        setOffset(Math.max(0, offset - PAGE_SIZE))
        return
      }
      setItems(data.results || [])
      setCount(data.count || 0)
      setError('')
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to load company activity logs. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [filters, offset])

  useEffect(() => { load() }, [load])
  const setFilter = (name, value) => { setOffset(0); setFilters((current) => ({ ...current, [name]: value })) }

  return <ClientLayout><main className="mx-auto w-full max-w-7xl p-5">
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-semibold text-[var(--color-ink)]">Company Activity Log</h1><p className="mt-1 text-sm text-[var(--color-muted)]">Company-wide manual and automated activity. Routine automated entries are retained for 30 days.</p></div>
      <button onClick={load} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 font-medium text-white disabled:opacity-50" disabled={loading}>Refresh</button>
    </header>
    <section className="mb-4 flex flex-wrap gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <select aria-label="Filter by module" value={filters.module} onChange={(event) => setFilter('module', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="">All modules</option><option value="email">Email</option><option value="scheduler">Scheduler</option><option value="ocr">OCR</option><option value="ai">AI</option><option value="netsuite">NetSuite</option><option value="auth">Authentication</option></select>
      <select aria-label="Filter by type" value={filters.activity_type} onChange={(event) => setFilter('activity_type', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="">Manual and automated</option><option value="manual">Manual</option><option value="automated">Automated</option></select>
      <select aria-label="Filter by status" value={filters.status} onChange={(event) => setFilter('status', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="">All statuses</option><option value="success">Success</option><option value="failed">Failed</option><option value="info">Info</option></select>
    </section>
    {error && <p role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <section className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]"><tr><th className="p-3">Time</th><th className="p-3">Module</th><th className="p-3">Activity</th><th className="p-3">Type</th><th className="p-3">User</th><th className="p-3">Status</th><th className="p-3">Details</th></tr></thead><tbody>
        {loading && <tr><td colSpan="7" className="p-5 text-[var(--color-muted)]">Loading activity logs...</td></tr>}
        {!loading && !items.length && <tr><td colSpan="7" className="p-5 text-[var(--color-muted)]">No activity logs match these filters.</td></tr>}
        {items.map((item) => <tr key={item.id} className="border-b border-[var(--color-border)] last:border-0"><td className="whitespace-nowrap p-3 text-[var(--color-muted)]">{new Date(item.created_at).toLocaleString()}</td><td className="p-3">{titleCase(item.module)}</td><td className="p-3 text-[var(--color-ink)]">{item.activity}</td><td className="p-3">{titleCase(item.activity_type)}</td><td className="p-3">{item.user_name || '—'}</td><td className="p-3"><span className={item.status === 'failed' ? 'text-red-600' : item.status === 'success' ? 'text-emerald-600' : 'text-[var(--color-muted)]'}>{titleCase(item.status)}</span></td><td className="max-w-xs p-3"><p className="truncate text-[var(--color-muted)]" title={item.summary}>{item.summary}</p><button onClick={() => setSelected(item)} className="mt-1 text-[var(--color-primary)]">View full details</button></td></tr>)}
      </tbody></table></div>
      <footer className="flex items-center justify-between border-t border-[var(--color-border)] p-4 text-sm text-[var(--color-muted)]"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded-lg border border-[var(--color-border)] px-3 py-1 disabled:opacity-40">Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, count)} of ${count}` : '0'}</span><button disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded-lg border border-[var(--color-border)] px-3 py-1 disabled:opacity-40">Next</button></footer>
    </section>
    {selected && <div role="dialog" aria-modal="true" aria-label="Activity log details" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"><section className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-xl bg-[var(--color-surface)] p-5 shadow-xl"><div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[var(--color-ink)]">Activity details</h2><button className="rounded-lg border border-[var(--color-border)] px-3 py-1" onClick={() => setSelected(null)}>Close</button></div><pre className="whitespace-pre-wrap break-words rounded-lg bg-[var(--color-surface-muted)] p-4 text-xs text-[var(--color-ink)]">{JSON.stringify(selected.detail, null, 2)}</pre></section></div>}
  </main></ClientLayout>
}
