import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY_CATEGORY_FORM = {
  name: '',
  route: '',
  query_param: '',
  center_tab_id: '',
  sort_order: '',
}

const EMPTY_PAGINATION = {
  page: 1,
  page_size: 10,
  total: 0,
  total_pages: 1,
  has_next: false,
  has_previous: false,
}

const firstQueryParamKey = (queryParams) =>
  queryParams && typeof queryParams === 'object'
    ? Object.keys(queryParams)[0] || ''
    : ''

export default function CenterCategoriesPage() {
  const navigate = useNavigate()

  const [categories, setCategories] = useState([])
  const [centerTabs, setCenterTabs] = useState([])
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState(EMPTY_PAGINATION)

  const [loading, setLoading] = useState(true)
  const [savingCategory, setSavingCategory] = useState(false)
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [editingCategoryId, setEditingCategoryId] = useState(null)
  const [categoryForm, setCategoryForm] = useState(EMPTY_CATEGORY_FORM)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadCategories = async (nextPage = page) => {
    setLoading(true)
    setError('')

    try {
      const result = await clientApi.getCenterCategories(nextPage)

      const nextCategories = result?.results || []
      setCategories(nextCategories)
      setCenterTabs(result?.center_tabs || [])
      setPagination(result?.pagination || {
        ...EMPTY_PAGINATION,
        page: nextPage,
      })

    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to load Center Categories.',
      )
      setCategories([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCategories(page)
  }, [page])

  const startCreateCategory = () => {
    setEditingCategoryId(null)
    setCategoryForm(EMPTY_CATEGORY_FORM)
    setShowCategoryForm(true)
    setError('')
    setMessage('')
  }

  const startEditCategory = (category) => {
    setEditingCategoryId(category.id)
    setCategoryForm({
      name: category.name || '',
      route: category.route || '',
      query_param:
        category.query_param ||
        firstQueryParamKey(category.query_params),
      center_tab_id: category.center_tab?.id || '',
      sort_order:
        category.sort_order === null ||
        category.sort_order === undefined
          ? ''
          : String(category.sort_order),
    })
    setShowCategoryForm(true)
    setError('')
    setMessage('')
  }

  const parseSortOrder = (value) => {
    if (value.trim() === '') {
      return null
    }

    const parsed = Number(value)
    if (!Number.isInteger(parsed) || parsed < 0) {
      return null
    }

    return parsed
  }

  const submitCategory = async () => {
    const name = categoryForm.name.trim()
    const queryParam = categoryForm.query_param.trim()

    if (!name) {
      setError('Center Category name is required.')
      return
    }

    if (!categoryForm.center_tab_id) {
      setError('Center Tab is required.')
      return
    }

    const sortOrder = parseSortOrder(categoryForm.sort_order)
    if (
      categoryForm.sort_order.trim() !== '' &&
      sortOrder === null
    ) {
      setError('Sort Order must be a non-negative integer.')
      return
    }

    setSavingCategory(true)
    setError('')
    setMessage('')

    try {
      if (editingCategoryId) {
        const payload = {
          name,
          route: '',
          query_param: queryParam,
        }

        if (sortOrder !== null) {
          payload.sort_order = sortOrder
        }

        await clientApi.updateNavigationTab(
          'level2',
          editingCategoryId,
          payload,
        )

        setMessage('Center Category updated successfully.')
      } else {
        const payload = {
          name,
          route,
          center_tab_id: categoryForm.center_tab_id,
          query_param: queryParam,
        }

        if (sortOrder !== null) {
          payload.sort_order = sortOrder
        }

        await clientApi.createCenterCategory(payload)
        setMessage('Center Category created successfully.')
      }

      setCategoryForm(EMPTY_CATEGORY_FORM)
      setEditingCategoryId(null)
      setShowCategoryForm(false)

      await loadCategories(page)
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          `Unable to ${
            editingCategoryId ? 'update' : 'create'
          } Center Category.`,
      )
    } finally {
      setSavingCategory(false)
    }
  }

  return (
    <ClientLayout
      title="Center Categories"
      breadcrumb="Settings / Customize / Center Categories"
    >
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[var(--color-ink)]">
              Center Categories
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Manage Level-2 categories and their Level-3 navigation items.
            </p>
          </div>

          <button
            type="button"
            onClick={startCreateCategory}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
          >
            New Center Category
          </button>
        </div>

        {showCategoryForm && (
          <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-[var(--color-ink)]">
                {editingCategoryId
                  ? 'Edit Center Category'
                  : 'Create Center Category'}
              </h2>

              {editingCategoryId && (
                <span className="text-xs text-[var(--color-muted)]">
                  Key and Internal ID cannot be changed.
                </span>
              )}
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-5">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                  Center Category Name
                </label>
                <input
                  value={categoryForm.name}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  placeholder="e.g. Transactions"
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                  Center Tab
                </label>
                <select
                  value={categoryForm.center_tab_id}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      center_tab_id: event.target.value,
                    }))
                  }
                  disabled={Boolean(editingCategoryId)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm disabled:opacity-60"
                >
                  <option value="">Select Center Tab</option>
                  {centerTabs.map((tab) => (
                    <option key={tab.id} value={tab.id}>
                      {tab.name}
                    </option>
                  ))}
                </select>
              </div>


              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                  Query Param (key only)
                </label>
                <input
                  value={categoryForm.query_param}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      query_param: event.target.value,
                    }))
                  }
                  placeholder="e.g. transaction_type"
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
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
                  value={categoryForm.sort_order}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      sort_order: event.target.value,
                    }))
                  }
                  placeholder="Auto"
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
                />
              </div>
            </div>

            <p className="mt-3 text-xs text-[var(--color-muted)]">
              Query Param is only the key. Its value is automatically the current category name.
            </p>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCategoryForm(false)
                  setEditingCategoryId(null)
                  setCategoryForm(EMPTY_CATEGORY_FORM)
                }}
                className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={savingCategory}
                onClick={submitCategory}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {savingCategory
                  ? 'Saving...'
                  : editingCategoryId
                    ? 'Save Changes'
                    : 'Create Center Category'}
              </button>
            </div>
          </div>
        )}

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

        <div className="mt-5 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Internal ID
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Center Tab
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
                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Actions
                  </th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center text-[var(--color-muted)]"
                    >
                      Loading Center Categories...
                    </td>
                  </tr>
                ) : categories.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center text-[var(--color-muted)]"
                    >
                      No Center Categories found.
                    </td>
                  </tr>
                ) : (
                  categories.map((category) => (
                    <tr
                      key={category.id}
                      className="border-b border-[var(--color-border)] last:border-b-0"
                    >
                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.internal_id}
                      </td>

                      <td className="px-4 py-3 font-medium">
                        <button
                          type="button"
                          onClick={() => {
                            setError('')
                            setMessage('')
                            navigate(
                              `/app/settings/customize/center-categories/${category.id}`,
                            )
                          }}
                          className="text-[var(--color-primary)]"
                        >
                          {category.name}
                        </button>
                        {category.system && (
                          <span className="ml-2 rounded-full bg-[var(--color-canvas)] px-2 py-0.5 text-[10px] font-semibold text-[var(--color-muted)]">
                            System
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.center_tab?.name || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.effective_route || category.route || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.query_param || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.sort_order}
                      </td>

                      <td className="px-4 py-3">
                        <button
                          type="button"
                          disabled={category.system}
                          onClick={() => startEditCategory(category)}
                          className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-ink)] disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--color-border)] px-4 py-3">
            <p className="text-xs text-[var(--color-muted)]">
              Page {pagination.page} of {pagination.total_pages}
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                disabled={!pagination.has_previous || loading}
                onClick={() => setPage((current) => current - 1)}
                className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Previous
              </button>

              <button
                type="button"
                disabled={!pagination.has_next || loading}
                onClick={() => setPage((current) => current + 1)}
                className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>

      </div>
    </ClientLayout>
  )
}
