import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY_FORM = { name: '', route: '', sort_order: '' }

export default function CenterTabsPage() {
  const navigate = useNavigate()
  const [tabs, setTabs] = useState([])
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState({ page: 1, page_size: 10, total: 0, total_pages: 1, has_next: false, has_previous: false })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selectedIds, setSelectedIds] = useState([])

  const loadTabs = async (nextPage = page) => {
    setLoading(true)
    setError('')
    try {
      const result = await clientApi.getCenterTabs(nextPage)
      setTabs(result?.results || [])
      setPagination(result?.pagination || pagination)
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to load Center Tabs.')
      setTabs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTabs(page) }, [page])

  const resetForm = () => {
    setForm(EMPTY_FORM)
    setEditingId(null)
    setShowForm(false)
  }

  const submit = async () => {
    const name = form.name.trim()
    const route = form.route.trim()
    if (!name) return setError('Center Tab name is required.')
    if (!route) return setError('Path is required.')
    if (route.includes('?') || route.includes('#')) return setError('Do not enter query parameters in Path.')

    setSaving(true); setError(''); setMessage('')
    try {
      const payload = { name, route }
      if (form.sort_order !== '') payload.sort_order = Number(form.sort_order)
      if (editingId) {
        await clientApi.updateNavigationTab('top', editingId, payload)
        setMessage('Center Tab updated successfully.')
      } else {
        await clientApi.createNavigationTab({ ...payload, parent_level: 'root' })
        setMessage('Center Tab created successfully.')
      }
      resetForm()
      await loadTabs(page)
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to save Center Tab.')
    } finally { setSaving(false) }
  }

  const openTab = async (tab) => {
    setError(''); setMessage('')
    try {
      const result = await clientApi.getCenterTabChildren(tab.id)
      if (!(result?.results || []).length) {
        setError(`Center Tab "${tab.name}" has no Center Categories yet.`)
        return
      }
      navigate(`/app/settings/customize/center-tabs/${tab.id}`)
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to open Center Tab.')
    }
  }

  const editTab = (tab) => {
    setEditingId(tab.id)
    setForm({ name: tab.name || '', route: tab.route || '', sort_order: tab.sort_order ?? '' })
    setShowForm(true); setError(''); setMessage('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const toggleSelected = (id) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  const toggleAll = () => {
    setSelectedIds((current) =>
      current.length === tabs.length ? [] : tabs.map((tab) => tab.id),
    )
  }

  const deleteSelected = async () => {
    if (!selectedIds.length) return
    if (!window.confirm(`Delete ${selectedIds.length} selected Center Tab(s) and all of their categories/subtabs?`)) return
    setDeleting(true); setError(''); setMessage('')
    try {
      await clientApi.deleteCenterTabs(selectedIds)
      setSelectedIds([])
      setMessage('Selected Center Tabs deleted successfully.')
      await loadTabs(page)
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to delete selected Center Tabs.')
    } finally { setDeleting(false) }
  }



  return (
    <ClientLayout title="Center Tabs" breadcrumb="Settings / Customize / Center Tabs">
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div><h1 className="text-xl font-semibold text-[var(--color-ink)]">Center Tabs</h1><p className="mt-1 text-sm text-[var(--color-muted)]">Click a Center Tab to manage its Center Categories.</p></div>
          <button type="button" onClick={() => { setShowForm((v) => !v); setEditingId(null); setForm(EMPTY_FORM); setError(''); setMessage('') }} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white">New Center Tab</button>
        </div>

        {showForm && (
          <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-ink)]">{editingId ? 'Edit Center Tab' : 'Create Center Tab'}</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <input aria-label="Center Tab Name" value={form.name} onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))} placeholder="Center Tab Name" className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm" />
              <input aria-label="Path" value={form.route} onChange={(e) => setForm((v) => ({ ...v, route: e.target.value }))} placeholder="Path e.g. /app/sales" className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm" />
              <input aria-label="Sort Order" type="number" min="0" value={form.sort_order} onChange={(e) => setForm((v) => ({ ...v, sort_order: e.target.value }))} placeholder="Sort Order" className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm" />
            </div>
            <div className="mt-4 flex justify-end gap-2"><button type="button" onClick={resetForm} className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold">Cancel</button><button type="button" disabled={saving} onClick={submit} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving...' : editingId ? 'Update Center Tab' : 'Create Center Tab'}</button></div>
          </div>
        )}

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {message && <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}

        <div className="mt-5 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
            <div className="text-sm font-semibold text-[var(--color-ink)]">Center Tabs</div>
            {selectedIds.length > 0 && <button type="button" disabled={deleting} onClick={deleteSelected} className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 disabled:opacity-50">{deleting ? 'Deleting...' : `Delete Selected (${selectedIds.length})`}</button>}
          </div>
          <div className="overflow-x-auto"><table className="min-w-full text-sm">
            <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]"><tr><th className="w-10 px-4 py-3 text-left"><input type="checkbox" checked={tabs.length > 0 && selectedIds.length === tabs.length} onChange={toggleAll} aria-label="Select all Center Tabs" /></th><th className="px-4 py-3 text-left">Internal ID</th><th className="px-4 py-3 text-left">Center Tab</th><th className="px-4 py-3 text-left">Path</th><th className="px-4 py-3 text-left">Sort Order</th><th className="px-4 py-3 text-right">Actions</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={6} className="px-4 py-8 text-center">Loading Center Tabs...</td></tr> : tabs.length === 0 ? <tr><td colSpan={6} className="px-4 py-8 text-center">No Center Tabs found.</td></tr> : tabs.map((tab) => (
                <tr key={tab.id} className="border-b border-[var(--color-border)] last:border-b-0">
                  <td className="px-4 py-3"><input type="checkbox" checked={selectedIds.includes(tab.id)} onChange={() => toggleSelected(tab.id)} aria-label={`Select ${tab.name}`} /></td>
                  <td className="px-4 py-3">{tab.internal_id ?? '—'}</td>
                  <td className="px-4 py-3 font-medium"><button type="button" onClick={() => openTab(tab)} className="text-[var(--color-primary)] hover:underline">{tab.name}</button></td>
                  <td className="px-4 py-3 text-[var(--color-ink-soft)]">{tab.route || '—'}</td>
                  <td className="px-4 py-3">{tab.sort_order ?? '—'}</td>
                  <td className="px-4 py-3 text-right"><button type="button" onClick={() => editTab(tab)} className="rounded-md border px-3 py-1.5 text-xs font-semibold">Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <div className="flex items-center justify-between border-t border-[var(--color-border)] px-4 py-3"><p className="text-xs text-[var(--color-muted)]">Page {pagination.page} of {pagination.total_pages}</p><div className="flex gap-2"><button type="button" disabled={!pagination.has_previous || loading} onClick={() => setPage((v) => v - 1)} className="rounded-lg border px-3 py-1.5 text-xs font-semibold disabled:opacity-40">Previous</button><button type="button" disabled={!pagination.has_next || loading} onClick={() => setPage((v) => v + 1)} className="rounded-lg border px-3 py-1.5 text-xs font-semibold disabled:opacity-40">Next</button></div></div>
        </div>
      </div>
    </ClientLayout>
  )
}
