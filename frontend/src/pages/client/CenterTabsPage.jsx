import { useEffect, useState } from 'react'
// import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const EMPTY_FORM = {
  name: '',
  route: '',
}

export default function CenterTabsPage() {
//   const navigate = useNavigate()
  const [tabs, setTabs] = useState([])
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 1,
    has_next: false,
    has_previous: false,
  })

  const [deleteMode, setDeleteMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState([])
  const [deleting, setDeleting] = useState(false)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selectedTab, setSelectedTab] = useState(null)
  const [tabCategories, setTabCategories] = useState([])
  const [loadingCategories, setLoadingCategories] = useState(false)

  const loadTabs = async (nextPage = page) => {
    setLoading(true)
    setError('')

    try {
      const result = await clientApi.getCenterTabs(nextPage)

      const nextTabs = result?.results || []
      const nextPagination = result?.pagination || {
        page: nextPage,
        page_size: 10,
        total: 0,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      }

      setTabs(nextTabs)
      setPagination(nextPagination)
      setSelectedIds((current) =>
        current.filter((id) =>
          nextTabs.some((tab) => String(tab.id) === String(id))
        )
      )
    } catch (err) {
      setError(
        err?.payload?.message ||
        err?.message ||
        'Unable to load Center Tabs.',
      )
      setTabs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTabs(page)
  }, [page])

  const toggleTabSelection = (tabId) => {
    const id = String(tabId)

    setSelectedIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    )
  }

  const toggleSelectAll = (checked) => {
    if (checked) {
      setSelectedIds(tabs.map((tab) => String(tab.id)))
    } else {
      setSelectedIds([])
    }
  }

  const exitDeleteMode = () => {
    setDeleteMode(false)
    setSelectedIds([])
    setError('')
  }

  const deleteSelectedTabs = async () => {
    if (!selectedIds.length || deleting) {
      return
    }

    if (
      !window.confirm(
        `Delete ${selectedIds.length} selected Center Tab(s)?`,
      )
    ) {
      return
    }

    setDeleting(true)
    setError('')
    setMessage('')

    try {
      await clientApi.deleteCenterTabs(selectedIds)

      const nextPage =
        tabs.length === selectedIds.length && page > 1
          ? page - 1
          : page

      setSelectedIds([])
      setDeleteMode(false)

      if (nextPage !== page) {
        setPage(nextPage)
      } else {
        await loadTabs(page)
      }

      setMessage('Selected Center Tabs deleted successfully.')
    } catch (err) {
      setError(
        err?.payload?.message ||
        err?.message ||
        'Unable to delete selected Center Tabs.',
      )
    } finally {
      setDeleting(false)
    }
  }

  const selectCenterTab = async (tab) => {
  if (deleteMode) {
    return
  }

  setSelectedTab(tab)
  setTabCategories([])
  setError('')
  setMessage('')
  setLoadingCategories(true)

  try {
    const result = await clientApi.getNavigationMenu()

    const selected = (result || []).find(
      (item) => String(item.id) === String(tab.id),
    )

    const categories = selected?.children || []

    if (categories.length === 0) {
      setError(`No Center Category available for ${tab.name}`)
      return
    }

    setTabCategories(categories)
  } catch (err) {
    setError(
      err?.payload?.message ||
        err?.message ||
        `Unable to load Center Category items for ${tab.name}.`,
    )
  } finally {
    setLoadingCategories(false)
  }
}

  const createCenterTab = async () => {
    const name = form.name.trim()
    const route = form.route.trim()

    if (!name) {
      setError('Center Tab name is required.')
      return
    }

    setSaving(true)
    setError('')
    setMessage('')

    try {
      await clientApi.createCenterTab({
        name,
        route,
      })

      setForm(EMPTY_FORM)
      setShowForm(false)
      setMessage('Center Tab created successfully.')

      if (page !== 1) {
        setPage(1)
      } else {
        await loadTabs(1)
      }
    } catch (err) {
      setError(
        err?.payload?.message ||
        err?.message ||
        'Unable to create Center Tab.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <ClientLayout
      title="Center Tabs"
      breadcrumb="Settings / Customize / Center Tabs"
    >
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[var(--color-ink)]">
              Center Tabs
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Manage top-level navigation tabs.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setShowForm((current) => !current)
                setForm(EMPTY_FORM)
                setError('')
                setMessage('')
              }}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white"
            >
              New Center Tab
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
                  onClick={deleteSelectedTabs}
                  disabled={!selectedIds.length || deleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {deleting ? 'Deleting...' : 'Delete Selected'}
                </button>
              </>
            )}
          </div>
        </div>
        {/* </div> */}

        {showForm && (
          <div className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="text-sm font-semibold text-[var(--color-ink)]">
              Create Center Tab
            </h2>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--color-ink-soft)]">
                  Center Tab Name
                </label>

                <input
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({
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
                  Path (optional)
                </label>

                <input
                  value={form.route}
                  onChange={(event) =>
                    setForm((current) => ({
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
                  setShowForm(false)
                  setForm(EMPTY_FORM)
                }}
                className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-ink-soft)]"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={saving}
                onClick={createCenterTab}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? 'Creating...' : 'Create Center Tab'}
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
                        aria-label="Select all Center Tabs on this page"
                        checked={
                          tabs.length > 0 &&
                          tabs.every((tab) =>
                            selectedIds.includes(String(tab.id))
                          )
                        }
                        onChange={(event) =>
                          toggleSelectAll(event.target.checked)
                        }
                      />
                    </th>
                  )}

                  <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
                    Center Tab Name
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
                      colSpan={deleteMode ? 3 : 2}
                      className="px-4 py-8 text-center text-sm text-[var(--color-muted)]"
                    >
                      Loading Center Tabs...
                    </td>
                  </tr>
                ) : tabs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={deleteMode ? 3 : 2}
                      className="px-4 py-8 text-center text-sm text-[var(--color-muted)]"
                    >
                      No Center Tabs found.
                    </td>
                  </tr>
                ) : (
                  tabs.map((tab) => (
                    <tr
                      key={tab.id}
                      className="border-b border-[var(--color-border)] last:border-b-0"
                    >
                      {deleteMode && (
                        <td className="w-12 px-4 py-3">
                          <input
                            type="checkbox"
                            aria-label={`Select ${tab.name}`}
                            checked={selectedIds.includes(String(tab.id))}
                            onChange={() => toggleTabSelection(tab.id)}
                          />
                        </td>
                      )}

                    <td className="px-4 py-3 font-medium">
                      <button
                        type="button"
                        disabled={deleteMode}
                        onClick={() => selectCenterTab(tab)}
                        className="text-[var(--color-primary)] hover:underline disabled:cursor-default disabled:no-underline"
                      >
                        {tab.name}
                      </button>
                    </td>

                      <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                        {tab.route || '—'}
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
        {selectedTab && !error?.includes('No Center Category item') && (
  <div className="mt-6 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
    <div className="border-b border-[var(--color-border)] px-4 py-4">
      <h2 className="text-sm font-semibold text-[var(--color-ink)]">
        {selectedTab.name}
      </h2>

      <p className="mt-1 text-xs text-[var(--color-muted)]">
        Center Category items
      </p>
    </div>

    {loadingCategories ? (
      <div className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">
        Loading Center Category items...
      </div>
    ) : (
      <table className="min-w-full text-sm">
        <thead className="border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
          <tr>
            <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
              Center Category Name
            </th>

            <th className="px-4 py-3 text-left font-semibold text-[var(--color-ink-soft)]">
              Path
            </th>
          </tr>
        </thead>

        <tbody>
          {tabCategories.map((category) => (
            <tr
              key={category.id}
              className="border-b border-[var(--color-border)] last:border-b-0"
            >
              <td className="px-4 py-3 font-medium text-[var(--color-ink)]">
                {category.name}
              </td>

              <td className="px-4 py-3 text-[var(--color-ink-soft)]">
                {category.route || '—'}
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