import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY_FORM = {
  name: '',
  route: '',
  query_param: '',
  sort_order: '',
}

const getQueryParamKey = (queryParams) =>
  queryParams && typeof queryParams === 'object'
    ? Object.keys(queryParams)[0] || ''
    : ''

export default function CenterCategoryDetailPage() {
  const { categoryId } = useParams()
  const [category, setCategory] = useState(null)
  const [children, setChildren] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')

    try {
      const result = await clientApi.getCenterCategoryChildren(categoryId)
      setCategory(result?.category || null)
      setChildren(result?.results || [])
      setSelectedIds([])
    } catch (err) {
      setCategory(null)
      setChildren([])
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to load Center Category.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [categoryId])

  const resetForm = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(EMPTY_FORM)
  }

  const startCreate = () => {
    resetForm()
    setShowForm(true)
    setError('')
    setMessage('')
  }

  const startEdit = (child) => {
    setEditingId(child.id)
    setForm({
      name: child.name || '',
      route: child.route || '',
      query_param:
        child.query_param || getQueryParamKey(child.query_params),
      sort_order:
        child.sort_order === null || child.sort_order === undefined
          ? ''
          : String(child.sort_order),
    })
    setShowForm(true)
    setError('')
    setMessage('')
  }

  const save = async () => {
    const name = form.name.trim()
    const queryParam = form.query_param.trim()

    if (!name) {
      setError('Level-3 name is required.')
      return
    }

    if (form.sort_order.trim() !== '') {
      const sortOrder = Number(form.sort_order)
      if (!Number.isInteger(sortOrder) || sortOrder < 0) {
        setError('Sort Order must be a non-negative integer.')
        return
      }
    }

    setSaving(true)
    setError('')
    setMessage('')

    try {
      const payload = {
        name,
        route: '',
        query_param: queryParam,
      }

      if (form.sort_order.trim() !== '') {
        payload.sort_order = Number(form.sort_order)
      }

      if (editingId) {
        await clientApi.updateNavigationTab(
          'level3',
          editingId,
          payload,
        )
        setMessage('Level-3 subtab updated successfully.')
      } else {
        await clientApi.createNavigationTab({
          ...payload,
          parent_level: 'level2',
          parent_id: categoryId,
        })
        setMessage('Level-3 subtab created successfully.')
      }

      resetForm()
      await load()
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          `Unable to ${editingId ? 'update' : 'create'} Level-3 subtab.`,
      )
    } finally {
      setSaving(false)
    }
  }

  const toggleSelected = (id) => {
    const value = String(id)
    setSelectedIds((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    )
  }

  const toggleAll = () => {
    setSelectedIds((current) =>
      current.length === children.length
        ? []
        : children.map((child) => String(child.id)),
    )
  }

  const deleteSelected = async () => {
    if (!selectedIds.length || deleting) return

    if (
      !window.confirm(
        `Delete ${selectedIds.length} selected Level-3 subtab(s)?`,
      )
    ) {
      return
    }

    setDeleting(true)
    setError('')
    setMessage('')

    try {
      await Promise.all(
        selectedIds.map((id) =>
          clientApi.deleteNavigationTab('level3', id),
        ),
      )
      setSelectedIds([])
      setMessage('Selected Level-3 subtabs deleted successfully.')
      await load()
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to delete selected Level-3 subtabs.',
      )
    } finally {
      setDeleting(false)
    }
  }

  const allSelected =
    children.length > 0 && selectedIds.length === children.length

  return (
    <ClientLayout
      title={category?.name || 'Center Category'}
      breadcrumb="Settings / Customize / Center Categories"
    >
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {loading ? (
          <p className="text-sm text-[var(--color-muted)]">Loading...</p>
        ) : !category ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            Center Category not found.
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <Link
                  to="/app/settings/customize/center-categories"
                  className="text-sm text-[var(--color-primary)]"
                >
                  ← Center Categories
                </Link>
                <h1 className="mt-2 text-xl font-semibold text-[var(--color-ink)]">
                  {category.name}
                </h1>
                <p className="mt-1 text-sm text-[var(--color-muted)]">
                  Manage Level-3 subtabs under this Center Category.
                </p>
              </div>

              <button
                type="button"
                onClick={startCreate}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
              >
                New Subtab
              </button>
            </div>

            {error && (
              <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            {message && (
              <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                {message}
              </p>
            )}

            {showForm && (
              <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
                <h2 className="text-sm font-semibold text-[var(--color-ink)]">
                  {editingId ? 'Edit Level-3 Subtab' : 'Create Level-3 Subtab'}
                </h2>

                <div className="mt-4 grid gap-4 md:grid-cols-4">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                      Name
                    </label>
                    <input
                      value={form.name}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                      placeholder="e.g. Sales Order"
                      className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm"
                    />
                  </div>


                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                      Query Param (key only)
                    </label>
                    <input
                      value={form.query_param}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          query_param: event.target.value,
                        }))
                      }
                      placeholder="e.g. record_type"
                      className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm"
                    />
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                      Sort Order
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={form.sort_order}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          sort_order: event.target.value,
                        }))
                      }
                      placeholder="Auto"
                      className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm"
                    />
                  </div>
                </div>

                <p className="mt-3 text-xs text-[var(--color-muted)]">
                  Path and Query Param are optional. When a Query Param is supplied, its value is automatically the subtab name.
                </p>

                <div className="mt-4 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={resetForm}
                    className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={save}
                    className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {saving
                      ? 'Saving...'
                      : editingId
                        ? 'Save Changes'
                        : 'Create Subtab'}
                  </button>
                </div>
              </div>
            )}

            <div className="mt-5 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
              <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-4">
                <h2 className="text-sm font-semibold text-[var(--color-ink)]">
                  Level-3 Subtabs
                </h2>
                {selectedIds.length > 0 && (
                  <button
                    type="button"
                    disabled={deleting}
                    onClick={deleteSelected}
                    className="rounded-lg border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 disabled:opacity-50"
                  >
                    {deleting
                      ? 'Deleting...'
                      : `Delete Selected (${selectedIds.length})`}
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
                    <tr>
                      <th className="w-10 px-4 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleAll}
                          aria-label="Select all Level-3 subtabs"
                        />
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                        Internal ID
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                        Subtab
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                        Path
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                        Query Param
                      </th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                        Sort Order
                      </th>
                      <th className="px-4 py-3 text-right font-semibold text-[var(--color-ink-soft)]">
                        Actions
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {children.length === 0 ? (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-4 py-8 text-center text-[var(--color-muted)]"
                        >
                          No Level-3 subtabs found.
                        </td>
                      </tr>
                    ) : (
                      children.map((child) => {
                        const queryParam =
                          child.query_param ||
                          getQueryParamKey(child.query_params)

                        return (
                          <tr
                            key={child.id}
                            className="border-b border-[var(--color-border)] last:border-b-0"
                          >
                            <td className="px-4 py-3">
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(String(child.id))}
                                onChange={() => toggleSelected(child.id)}
                                aria-label={`Select ${child.name}`}
                              />
                            </td>
                            <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                              {child.internal_id ?? '—'}
                            </td>
                            <td className="px-4 py-3 font-medium text-[var(--color-ink)]">
                              {child.name}
                            </td>
                            <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                              {child.effective_route || child.route || '—'}
                            </td>
                            <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                              {queryParam || '—'}
                            </td>
                            <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                              {child.sort_order ?? '—'}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => startEdit(child)}
                                className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-ink)]"
                              >
                                Edit
                              </button>
                            </td>
                          </tr>
                        )
                      })
                    )}
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
