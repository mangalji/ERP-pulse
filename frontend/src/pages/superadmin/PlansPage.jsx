import { useState, useEffect, useCallback, useRef } from 'react'
import { getCachedData, setCachedData } from '../../utils/pageCache.js'
import { useLocation, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import PaginationControls from '../../components/ui/PaginationControls.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'
import { formatDate } from '../../utils/formatDate.js'

const PAGE_SIZE = 10

const EMPTY_PLAN = {
  name: '',
  description: '',
  price: '',
  validity_days: 30,
}

export default function PlansPage() {
  const { toasts, addToast, removeToast } = useToast()

  const CACHE_KEY = 'superadmin:plans:default'
  const cached = useRef(getCachedData(CACHE_KEY)).current
  const firstLoad = useRef(true)

  const [rows, setRows] = useState(cached?.rows ?? [])
  const [count, setCount] = useState(cached?.count ?? 0)
  const [loading, setLoading] = useState(!cached)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_PLAN)
  const [saving, setSaving] = useState(false)
  const [confirm, setConfirm] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()
  const isCreatePage = location.pathname.endsWith('/new')

  const handlePlanAction = async () => {
    if (!confirm) return
    setSaving(true)
    try {
      await superadminApi.deletePlan(confirm.plan.id)
      addToast('Plan deleted successfully')
      setConfirm(null)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const load = useCallback(async () => {
    const isDefaultQuery = search === '' && offset === 0
    const silent = firstLoad.current && isDefaultQuery && Boolean(cached)
    firstLoad.current = false
    if (!silent) setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listPlans({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
      if (isDefaultQuery) setCachedData(CACHE_KEY, { rows: data.results || [], count: data.count || 0 })
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load plans')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [search, offset, cached])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (isCreatePage) {
      setForm(EMPTY_PLAN)
      setModal({ mode: 'create' })
    } else {
      setModal(null)
    }
  }, [isCreatePage])

  const openCreate = () => {
    navigate('/admin/plans/new')
  }

  const openEdit = (plan) => {
    navigate(`/admin/plans/${plan.id}/edit`)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (modal.mode === 'create') {
        await superadminApi.createPlan(form)
        addToast('Plan created successfully')
      } else {
        await superadminApi.updatePlan(modal.plan.id, form)
        addToast('Plan updated successfully')
      }
      navigate('/admin/plans')
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to save plan', 'error')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <button
          onClick={() => navigate(`/admin/plans/${row.id}`)}
          className="font-medium text-[var(--color-primary)] hover:underline"
        >
          {row.name}
        </button>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      render: (row) => <span className="font-mono-tabular text-[var(--color-ink-soft)]">Rs.{Number(row.price || 0).toFixed(2)}</span>,
    },
    {
      key: 'validity_days',
      header: 'Validity',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.validity_days ?? 30} days</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => <span className="text-[var(--color-muted)]">{row.created_at ? formatDate(row.created_at) : '—'}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => navigate(`/admin/plans/${row.id}`)}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
          >
            View
          </button>
          <button onClick={() => openEdit(row)} className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
            Edit
          </button>
          <button
            onClick={() => setConfirm({ plan: row, action: 'delete' })}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
          >
            Delete
          </button>
        </div>
      ),
    },
  ]

  return (
    <AdminLayout title="Plans" breadcrumb="Plans">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Dashboard</span>
        </div>
        <PageHeader
          title={isCreatePage ? 'Create Plan' : 'Plans'}
          subtitle={isCreatePage ? 'Configure pricing and validity for a subscription plan.' : 'Manage subscription plans and their validity.'}
          actions={isCreatePage ? <Button intent="secondary" onClick={() => navigate('/admin/plans')}>Back to Plans</Button> : <Button onClick={openCreate}>Create Plan</Button>}
        />

        {!isCreatePage && <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setOffset(0) }} placeholder="Search plans..." />
            <span className="text-xs text-[var(--color-muted)]">{count} result{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No plans found"
            emptyDescription="Create a plan to get started."
          />

          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            onPrevious={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            onNext={() => setOffset((o) => o + PAGE_SIZE)}
          />
        </Card>}
      </div>

      {/* Create/Edit Plan Modal */}
      {modal && (
        <div className={isCreatePage ? 'w-full' : 'fixed inset-0 z-50 flex items-center justify-center p-4'}>
          <div className={isCreatePage ? 'hidden' : 'absolute inset-0 bg-black/40'} onClick={() => navigate('/admin/plans')} />
          <div className={isCreatePage ? 'relative w-full max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm' : 'relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl'}>
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              {modal.mode === 'create' ? 'Create Plan' : 'Edit Plan'}
            </h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <Input label="Price (₹)" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
              <Input label="Validity (days)" type="number" value={form.validity_days} onChange={(e) => setForm({ ...form, validity_days: e.target.value })} />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={() => navigate('/admin/plans')}>Cancel</Button>
              <Button onClick={handleSave} isLoading={saving}>{modal.mode === 'create' ? 'Create' : 'Save'}</Button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? `Delete plan?` : ''}
        message={confirm ? `Are you sure you want to delete ${confirm?.plan?.name}?` : ''}
        confirmLabel="Delete"
        intent="negative"
        onConfirm={handlePlanAction}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
