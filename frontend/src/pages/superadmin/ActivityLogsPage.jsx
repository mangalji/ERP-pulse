import { useCallback, useEffect, useState } from 'react'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import apiClient from '../../services/apiClient.js'
import { formatDateTime } from '../../utils/formatDate.js'

const PAGE_SIZE = 25
const titleCase = (value) => String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

export default function ActivityLogsPage() {
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState({ company: '', module: '', status: '', activity_type: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await apiClient.get('/audit/events/', { params: { offset, limit: PAGE_SIZE, ...filters } })
      const data = response.data
      setItems(data.results || [])
      setCount(data.count || 0)
      setError('')
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to load activity logs.')
    } finally {
      setLoading(false)
    }
  }, [filters, offset])

  useEffect(() => { void load() }, [load])
  const setFilter = (name, value) => { setOffset(0); setFilters((current) => ({ ...current, [name]: value })) }

  return (
    <AdminLayout title="Company Logs" breadcrumb="Company Logs">
      <main className="mx-auto w-full max-w-7xl">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="text-2xl font-semibold text-[var(--color-ink)]">Company Logs</h1><p className="mt-1 text-sm text-[var(--color-muted)]">Cross-company manual and automated activity logs.</p></div>
          <Button size="sm" onClick={load} disabled={loading}>Refresh</Button>
        </div>
        <Card className="mb-4 flex flex-wrap gap-3 p-4">
          <input aria-label="Search company" placeholder="Search company" value={filters.company} onChange={(event) => setFilter('company', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)]" />
          <select aria-label="Filter by module" value={filters.module} onChange={(event) => setFilter('module', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-ink)]"><option value="">All modules</option><option value="company">Company</option><option value="employee">Employee</option><option value="email">Email</option><option value="scheduler">Scheduler</option><option value="ocr">OCR</option><option value="ai">AI</option><option value="netsuite">NetSuite</option><option value="auth">Authentication</option></select>
          <select aria-label="Filter by type" value={filters.activity_type} onChange={(event) => setFilter('activity_type', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-ink)]"><option value="">Manual and automated</option><option value="manual">Manual</option><option value="automated">Automated</option></select>
          <select aria-label="Filter by status" value={filters.status} onChange={(event) => setFilter('status', event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-ink)]"><option value="">All statuses</option><option value="success">Success</option><option value="failed">Failed</option><option value="info">Info</option></select>
        </Card>
        {error && <p role="alert" className="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]"><tr><th className="p-3">Time</th><th className="p-3">Company</th><th className="p-3">Module</th><th className="p-3">Activity</th><th className="p-3">Type</th><th className="p-3">User</th><th className="p-3">Status</th><th className="p-3">Details</th></tr></thead><tbody>
            {loading && <tr><td colSpan="8" className="p-5 text-[var(--color-muted)]">Loading activity logs...</td></tr>}
            {!loading && !items.length && <tr><td colSpan="8" className="p-5 text-[var(--color-muted)]">No activity logs match these filters.</td></tr>}
            {items.map((item) => <tr key={item.id} className="border-b border-[var(--color-border)] last:border-0"><td className="whitespace-nowrap p-3 text-[var(--color-muted)]">{formatDateTime(item.created_at)}</td><td className="p-3 font-medium">{item.company_name}</td><td className="p-3">{titleCase(item.module)}</td><td className="p-3">{item.activity}</td><td className="p-3">{titleCase(item.activity_type)}</td><td className="p-3">{item.user_name || '—'}</td><td className="p-3"><span className={item.status === 'failed' ? 'text-red-600' : item.status === 'success' ? 'text-emerald-600' : 'text-[var(--color-muted)]'}>{titleCase(item.status)}</span></td><td className="max-w-xs p-3"><p className="truncate text-[var(--color-muted)]" title={item.summary}>{item.summary}</p><button onClick={() => setSelected(item)} className="mt-1 text-[var(--color-primary)]">View details</button></td></tr>)}
          </tbody></table></div>
          <footer className="flex items-center justify-between border-t border-[var(--color-border)] p-4 text-sm text-[var(--color-muted)]"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} className="rounded-lg border border-[var(--color-border)] px-3 py-1 disabled:opacity-40">Previous</button><span>{count ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, count)} of ${count}` : '0'}</span><button disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset(offset + PAGE_SIZE)} className="rounded-lg border border-[var(--color-border)] px-3 py-1 disabled:opacity-40">Next</button></footer>
        </Card>
        {selected && <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"><section className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-xl bg-[var(--color-surface)] p-5 shadow-xl"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-[var(--color-ink)]">Activity details</h2><button onClick={() => setSelected(null)} className="rounded-lg border border-[var(--color-border)] px-3 py-1">Close</button></div><pre className="whitespace-pre-wrap break-words rounded-lg bg-[var(--color-surface-muted)] p-4 text-xs">{JSON.stringify(selected.detail, null, 2)}</pre></section></div>}
      </main>
    </AdminLayout>
  )
}
