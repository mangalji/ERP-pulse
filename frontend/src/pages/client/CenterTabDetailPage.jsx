import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY = { name: '', route: '', query_param: '', sort_order: '' }

export default function CenterTabDetailPage() {
  const { tabId } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState(null)
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await clientApi.getCenterTabChildren(tabId)
      setTab(result?.center_tab || null)
      setCategories(result?.results || [])
      setSelectedIds([])
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to load Center Tab.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [tabId])

  const reset = () => {
    setEditingId(null)
    setForm(EMPTY)
    setShowForm(false)
  }

  const save = async () => {
    if (!form.name.trim()) return setError('Center Category name is required.')

    setSaving(true)
    setError('')
    setMessage('')
    try {
      const payload = {
        name: form.name.trim(),
        route: form.route.trim(),
        query_param: form.query_param.trim(),
      }
      if (form.sort_order !== '') payload.sort_order = Number(form.sort_order)

      if (editingId) {
        await clientApi.updateNavigationTab('level2', editingId, payload)
        setMessage('Center Category updated successfully.')
      } else {
        await clientApi.createNavigationTab({
          ...payload,
          parent_level: 'top',
          parent_id: tabId,
        })
        setMessage('Center Category created successfully.')
      }

      reset()
      await load()
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to save Center Category.')
    } finally {
      setSaving(false)
    }
  }

  const startEdit = (category) => {
    const queryParam = Object.keys(category.query_params || {})[0] || ''
    setEditingId(category.id)
    setForm({
      name: category.name || '',
      route: category.route || '',
      query_param: queryParam,
      sort_order: category.sort_order ?? '',
    })
    setShowForm(true)
    setError('')
    setMessage('')
  }

  const openCategory = async (category) => {
    setError('')
    setMessage('')
    try {
      const result = await clientApi.getCenterCategoryChildren(category.id)
      if (!(result?.results || []).length) {
        setError(`Center Category "${category.name}" has no subtabs yet.`)
        return
      }
      navigate(`/app/settings/customize/center-categories/${category.id}`)
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to open Center Category.')
    }
  }

  const toggleSelected = (id) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  const toggleAll = () => {
    setSelectedIds((current) =>
      current.length === categories.length ? [] : categories.map((category) => category.id),
    )
  }

  const deleteSelected = async () => {
    if (!selectedIds.length) return
    if (!window.confirm(`Delete ${selectedIds.length} selected Center Category(s) and their subtabs?`)) return

    setDeleting(true)
    setError('')
    setMessage('')
    try {
      await clientApi.deleteCenterCategories(selectedIds)
      setSelectedIds([])
      setMessage('Selected Center Categories deleted successfully.')
      await load()
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to delete selected Center Categories.')
    } finally {
      setDeleting(false)
    }
  }

  const allSelected = categories.length > 0 && selectedIds.length === categories.length

  return (
    <ClientLayout title={tab?.name || 'Center Tab'} breadcrumb="Settings / Customize / Center Tabs">
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        {loading ? (
          <p className="text-sm text-[var(--color-muted)]">Loading...</p>
        ) : !tab ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">Center Tab not found.</p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <div>
                <Link to="/app/settings/customize/center-tabs" className="text-sm text-[var(--color-primary)]">
                  ← Center Tabs
                </Link>
                <h1 className="mt-2 text-xl font-semibold text-[var(--color-ink)]">{tab.name}</h1>
                <p className="mt-1 text-sm text-[var(--color-muted)]">
                  Manage Center Categories under this Center Tab.
                </p>
              </div>

              <button
                type="button"
                onClick={() => { reset(); setShowForm(true); setError(''); setMessage('') }}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
              >
                New Center Category
              </button>
            </div>

            {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            {message && <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}

            {showForm && (
              <div className="mt-5 border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <h2 className="text-sm font-semibold text-[var(--color-ink)]">
                  {editingId ? 'Edit Center Category' : 'Create Center Category'}
                </h2>

                <div className="mt-4 grid gap-3 sm:grid-cols-4">
                  <input value={form.name} onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))} placeholder="Name" className="rounded-md border px-3 py-2 text-sm" />
                  <input value={form.route} onChange={(e) => setForm((v) => ({ ...v, route: e.target.value }))} placeholder="Path (optional)" className="rounded-md border px-3 py-2 text-sm" />
                  <input value={form.query_param} onChange={(e) => setForm((v) => ({ ...v, query_param: e.target.value }))} placeholder="Query Param key (optional)" className="rounded-md border px-3 py-2 text-sm" />
                  <input type="number" min="0" value={form.sort_order} onChange={(e) => setForm((v) => ({ ...v, sort_order: e.target.value }))} placeholder="Sort Order" className="rounded-md border px-3 py-2 text-sm" />
                </div>

                <div className="mt-4 flex justify-end gap-2">
                  <button type="button" onClick={reset} className="rounded-md border px-3 py-2 text-sm">Cancel</button>
                  <button type="button" disabled={saving} onClick={save} className="rounded-md bg-[var(--color-primary)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
                    {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                  </button>
                </div>
              </div>
            )}

            <div className="mt-5 overflow-hidden border border-[var(--color-border)] bg-[var(--color-surface)]">
              <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
                <div className="text-sm font-semibold text-[var(--color-ink)]">Center Categories</div>
                {selectedIds.length > 0 && (
                  <button
                    type="button"
                    disabled={deleting}
                    onClick={deleteSelected}
                    className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 disabled:opacity-50"
                  >
                    {deleting ? 'Deleting...' : `Delete Selected (${selectedIds.length})`}
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
                    <tr>
                      <th className="w-10 px-4 py-3 text-left">
                        <input type="checkbox" checked={allSelected} onChange={toggleAll} aria-label="Select all Center Categories" />
                      </th>
                      <th className="px-4 py-3 text-left">Internal ID</th>
                      <th className="px-4 py-3 text-left">Center Category</th>
                      <th className="px-4 py-3 text-left">Path</th>
                      <th className="px-4 py-3 text-left">Query Param</th>
                      <th className="px-4 py-3 text-left">Sort Order</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-[var(--color-muted)]">
                          No Center Categories found.
                        </td>
                      </tr>
                    ) : categories.map((category) => {
                      const queryParam = Object.keys(category.query_params || {})[0] || ''
                      return (
                        <tr key={category.id} className="border-b border-[var(--color-border)] last:border-b-0">
                          <td className="px-4 py-3">
                            <input type="checkbox" checked={selectedIds.includes(category.id)} onChange={() => toggleSelected(category.id)} aria-label={`Select ${category.name}`} />
                          </td>
                          <td className="px-4 py-3">{category.internal_id ?? '—'}</td>
                          <td className="px-4 py-3 font-medium">
                            <button type="button" onClick={() => openCategory(category)} className="text-[var(--color-primary)] hover:underline">
                              {category.name}
                            </button>
                          </td>
                          <td className="px-4 py-3">{category.route || '—'}</td>
                          <td className="px-4 py-3">{queryParam || '—'}</td>
                          <td className="px-4 py-3">{category.sort_order ?? '—'}</td>
                          <td className="px-4 py-3 text-right">
                            <button type="button" onClick={() => startEdit(category)} className="rounded-md border px-3 py-1.5 text-xs font-semibold">
                              Edit
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </ClientLayout>
  )
}
