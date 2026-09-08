import { useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY_CATEGORY_FORM = {
  name: '',
  route: '',
  center_tab_id: '',
}

const EMPTY_CHILD_FORM = {
  name: '',
  route: '',
}

export default function CenterCategoriesPage() {
  const [categories, setCategories] = useState([])
  const [centerTabs, setCenterTabs] = useState([])

  const [page, setPage] = useState(1)

  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 1,
    has_next: false,
    has_previous: false,
  })

  const [selectedCategory, setSelectedCategory] = useState(null)
  const [children, setChildren] = useState([])

  const [loading, setLoading] = useState(true)
  const [loadingChildren, setLoadingChildren] = useState(false)

  const [savingCategory, setSavingCategory] = useState(false)
  const [savingChild, setSavingChild] = useState(false)

  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [showChildForm, setShowChildForm] = useState(false)

  const [categoryForm, setCategoryForm] = useState(
    EMPTY_CATEGORY_FORM,
  )

  const [childForm, setChildForm] = useState(
    EMPTY_CHILD_FORM,
  )

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const [deleteMode, setDeleteMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState([])
  const [deleting, setDeleting] = useState(false)

  const loadCategories = async (nextPage = 1) => {
    setLoading(true)
    setError('')

    try {
      const result = await clientApi.getCenterCategories(nextPage)

      const nextCategories = result?.results || []
      const nextPagination = result?.pagination || {
        page: nextPage,
        page_size: 10,
        total: 0,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      }

      setCategories(nextCategories)
      setCenterTabs(result?.center_tabs || [])
      setPagination(nextPagination)
      setSelectedIds((current) =>
        current.filter((id) =>
          nextCategories.some(
            (category) => String(category.id) === String(id)
          )
        )
      )
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

  const toggleCategorySelection = (categoryId) => {
    const id = String(categoryId)

    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    )
  }

  const toggleSelectAll = (checked) => {
    if (checked) {
      setSelectedIds(
        categories.map((category) => String(category.id))
      )
    } else {
      setSelectedIds([])
    }
  }

  const exitDeleteMode = () => {
    setDeleteMode(false)
    setSelectedIds([])
    setError('')
  }

  const deleteSelectedCategories = async () => {
    if (!selectedIds.length || deleting) {
      return
    }

    if (
      !window.confirm(
        `Delete ${selectedIds.length} selected Center Category(s)?`,
      )
    ) {
      return
    }

    setDeleting(true)
    setError('')
    setMessage('')

    try {
      await clientApi.deleteCenterCategories(selectedIds)

      const deletingCurrentCategory =
        selectedCategory &&
        selectedIds.includes(String(selectedCategory.id))

      const nextPage =
        categories.length === selectedIds.length && page > 1
          ? page - 1
          : page

      setSelectedIds([])
      setDeleteMode(false)

      if (deletingCurrentCategory) {
        setSelectedCategory(null)
        setChildren([])
        setShowChildForm(false)
        setChildForm(EMPTY_CHILD_FORM)
      }

      if (nextPage !== page) {
        setPage(nextPage)
      } else {
        await loadCategories(page)
      }

      setMessage('Selected Center Categories deleted successfully.')
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to delete selected Center Categories.',
      )
    } finally {
      setDeleting(false)
    }
  }

  const selectCategory = async (category) => {
    setSelectedCategory(category)
    setChildren([])
    setShowChildForm(false)
    setChildForm(EMPTY_CHILD_FORM)

    setLoadingChildren(true)
    setError('')

    try {
      const result =
        await clientApi.getCenterCategoryChildren(category.id)

      setChildren(result?.results || [])
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to load Level-3 items.',
      )
    } finally {
      setLoadingChildren(false)
    }
  }

  const createCategory = async () => {
    const name = categoryForm.name.trim()

    if (!name) {
      setError('Center Category name is required.')
      return
    }

    if (!categoryForm.center_tab_id) {
      setError('Center Tab is required.')
      return
    }

    setSavingCategory(true)
    setError('')
    setMessage('')

    try {
      await clientApi.createCenterCategory({
        name,
        route: categoryForm.route.trim(),
        center_tab_id: categoryForm.center_tab_id,
      })

      setCategoryForm(EMPTY_CATEGORY_FORM)
      setShowCategoryForm(false)
      setMessage('Center Category created successfully.')

      if (page !== 1) {
        setPage(1)
      } else {
        await loadCategories(1)
      }
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to create Center Category.',
      )
    } finally {
      setSavingCategory(false)
    }
  }

  const createChild = async () => {
    if (!selectedCategory) {
      return
    }

    const name = childForm.name.trim()

    if (!name) {
      setError('Level-3 name is required.')
      return
    }

    setSavingChild(true)
    setError('')
    setMessage('')

    try {
      await clientApi.createCenterCategoryChild(
        selectedCategory.id,
        {
          name,
          route: childForm.route.trim(),
        },
      )

      setChildForm(EMPTY_CHILD_FORM)
      setShowChildForm(false)
      setMessage('Level-3 item created successfully.')

      const result =
        await clientApi.getCenterCategoryChildren(
          selectedCategory.id,
        )

      setChildren(result?.results || [])
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to create Level-3 item.',
      )
    } finally {
      setSavingChild(false)
    }
  }

  return (
    <ClientLayout
      title="Center Categories"
      breadcrumb="Settings / Customize / Center Categories"
    >
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[var(--color-ink)]">
              Center Categories
            </h1>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Manage categories under Center Tabs.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setShowCategoryForm((current) => !current)
                setCategoryForm(EMPTY_CATEGORY_FORM)
                setError('')
                setMessage('')
              }}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
            >
              New Center Category
            </button>

            {!deleteMode ? (
              <button
                type="button"
                onClick={() => {
                  setDeleteMode(true)
                  setSelectedIds([])
                  setError('')
                  setMessage('')
                }}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-600"
              >
                Delete
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={exitDeleteMode}
                  disabled={deleting}
                  className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-ink-soft)] disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={deleteSelectedCategories}
                  disabled={!selectedIds.length || deleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {deleting ? 'Deleting...' : 'Delete Selected'}
                </button>
              </>
            )}
          </div>
        </div>

        {showCategoryForm && (
          <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-ink)]">
              Create Center Category
            </h2>

            <div className="mt-4 grid gap-4 sm:grid-cols-3">
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
                  placeholder="e.g. Sales"
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
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
                >
                  <option value="">
                    Select Center Tab
                  </option>

                  {centerTabs.map((tab) => (
                    <option key={tab.id} value={tab.id}>
                      {tab.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                  Path (optional)
                </label>

                <input
                  value={categoryForm.route}
                  onChange={(event) =>
                    setCategoryForm((current) => ({
                      ...current,
                      route: event.target.value,
                    }))
                  }
                  placeholder="e.g. /app/sales"
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
                />
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCategoryForm(false)
                  setCategoryForm(EMPTY_CATEGORY_FORM)
                }}
                className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={savingCategory}
                onClick={createCategory}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {savingCategory
                  ? 'Creating...'
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
                  {deleteMode && (
                    <th className="w-12 px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label="Select all Center Categories on this page"
                        checked={
                          categories.length > 0 &&
                          categories.every((category) =>
                            selectedIds.includes(String(category.id))
                          )
                        }
                        onChange={(event) =>
                          toggleSelectAll(event.target.checked)
                        }
                      />
                    </th>
                  )}

                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Center Category Name
                  </th>

                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Center Tab
                  </th>

                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Path
                  </th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={deleteMode ? 4 : 3}
                      className="px-4 py-8 text-center text-[var(--color-muted)]"
                    >
                      Loading Center Categories...
                    </td>
                  </tr>
                ) : categories.length === 0 ? (
                  <tr>
                    <td
                      colSpan={deleteMode ? 4 : 3}
                      className="px-4 py-8 text-center text-[var(--color-muted)]"
                    >
                      No Center Categories found.
                    </td>
                  </tr>
                ) : (
                  categories.map((category) => (
                    <tr
                      key={category.id}
                      className={`border-b border-[var(--color-border)] last:border-b-0 ${
                        selectedCategory?.id === category.id
                          ? 'bg-[var(--color-canvas)]'
                          : ''
                      }`}
                    >
                      {deleteMode && (
                        <td className="w-12 px-4 py-3">
                          <input
                            type="checkbox"
                            aria-label={`Select ${category.name}`}
                            checked={selectedIds.includes(String(category.id))}
                            onChange={() =>
                              toggleCategorySelection(category.id)
                            }
                          />
                        </td>
                      )}

                      <td className="px-4 py-3 font-medium">
                        <button
                          type="button"
                          onClick={() =>
                            selectCategory(category)
                          }
                          className="text-[var(--color-primary)]"
                        >
                          {category.name}
                        </button>
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.center_tab?.name || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {category.route || '—'}
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
                onClick={() =>
                  setPage((current) => current - 1)
                }
                className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Previous
              </button>

              <button
                type="button"
                disabled={!pagination.has_next || loading}
                onClick={() =>
                  setPage((current) => current + 1)
                }
                className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {selectedCategory && (
          <div className="mt-6 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-4">
              <div>
                <h2 className="text-sm font-semibold text-[var(--color-ink)]">
                  {selectedCategory.name}
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Level-3 items
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  setShowChildForm((current) => !current)
                  setChildForm(EMPTY_CHILD_FORM)
                  setError('')
                }}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
              >
                New
              </button>
            </div>

            {showChildForm && (
              <div className="border-b border-[var(--color-border)] p-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                      Name
                    </label>

                    <input
                      value={childForm.name}
                      onChange={(event) =>
                        setChildForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                      placeholder="Enter Level-3 name"
                      className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm"
                    />
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                      Path (optional)
                    </label>

                    <input
                      value={childForm.route}
                      onChange={(event) =>
                        setChildForm((current) => ({
                          ...current,
                          route: event.target.value,
                        }))
                      }
                      placeholder="Enter path"
                      className="w-full rounded-lg border border-[var(--color-border)] px-3 py-2.5 text-sm"
                    />
                  </div>
                </div>

                <div className="mt-4 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowChildForm(false)
                      setChildForm(EMPTY_CHILD_FORM)
                    }}
                    className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold"
                  >
                    Cancel
                  </button>

                  <button
                    type="button"
                    disabled={savingChild}
                    onClick={createChild}
                    className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {savingChild ? 'Creating...' : 'Create'}
                  </button>
                </div>
              </div>
            )}

            {loadingChildren ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">
                Loading Level-3 items...
              </div>
            ) : children.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">
                No Level-3 items found.
              </div>
            ) : (
              <table className="min-w-full text-sm">
                <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                      Name
                    </th>

                    <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                      Path
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {children.map((child) => (
                    <tr
                      key={child.id}
                      className="border-b border-[var(--color-border)] last:border-b-0"
                    >
                      <td className="px-4 py-3 font-medium text-[var(--color-ink)]">
                        {child.name}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {child.route || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </ClientLayout>
  )
}