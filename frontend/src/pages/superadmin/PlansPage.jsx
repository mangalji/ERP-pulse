import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

const PAGE_SIZE = 10

const EMPTY_PLAN = {
  name: '',
  description: '',
  monthly_price: '',
  yearly_price: '',
  max_employees: 0,
  max_ocr_documents: 0,
  max_storage_gb: 0,
  status: 'ACTIVE',
}

export default function PlansPage() {
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [modal, setModal] = useState(null) // null | {mode:'create'} | {mode:'edit', plan}
  const [form, setForm] = useState(EMPTY_PLAN)
  const [saving, setSaving] = useState(false)
  const [confirm, setConfirm] = useState(null)
  const navigate = useNavigate()

  const handlePlanAction = async () => {
    if (!confirm) return
    setSaving(true)
    try {
      if (confirm.action === 'activate') {
        await superadminApi.activatePlan(confirm.plan.id)
        addToast('Plan activated successfully')
      } else {
        await superadminApi.deactivatePlan(confirm.plan.id)
        addToast('Plan deactivated successfully')
      }
      setConfirm(null)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listPlans({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load plans')
    } finally {
      setLoading(false)
    }
  }, [search, offset])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setForm(EMPTY_PLAN)
    setModal({ mode: 'create' })
  }

  const openEdit = (plan) => {
    setForm({
      name: plan.name || '',
      description: plan.description || '',
      monthly_price: plan.monthly_price ?? '',
      yearly_price: plan.yearly_price ?? '',
      max_employees: plan.max_employees ?? 0,
      max_ocr_documents: plan.max_ocr_documents ?? 0,
      max_storage_gb: plan.max_storage_gb ?? 0,
      status: plan.status || 'ACTIVE',
    })
    setModal({ mode: 'edit', plan })
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
      setModal(null)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to save plan', 'error')
    } finally {
      setSaving(false)
    }
  }

  /* Old delete handler — kept for rollback
  const handleDelete = async () => {
    setSaving(true)
    try {
      await superadminApi.deletePlan(confirm.plan.id)
      addToast('Plan deleted successfully')
      setConfirm(null)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to delete plan', 'error')
    } finally {
      setSaving(false)
    }
  }
  */

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
      key: 'monthly_price',
      header: 'Monthly',
      render: (row) => <span className="font-mono-tabular text-[var(--color-ink-soft)]">${Number(row.monthly_price || 0).toFixed(2)}</span>,
    },
    {
      key: 'yearly_price',
      header: 'Yearly',
      render: (row) => <span className="font-mono-tabular text-[var(--color-ink-soft)]">${Number(row.yearly_price || 0).toFixed(2)}</span>,
    },
    {
      key: 'max_employees',
      header: 'Max Employees',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.max_employees ?? 0}</span>,
    },
    {
      key: 'enabled_models',
      header: 'Included Modules',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.enabled_models?.length ?? 0}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => <span className="text-[var(--color-muted)]">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</span>,
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
          {row.status === 'ACTIVE' ? (
            <button
              onClick={() => setConfirm({ plan: row, action: 'deactivate' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
            >
              Deactivate
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ plan: row, action: 'activate' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Activate
            </button>
          )}
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
          title="Plans"
          subtitle="Manage subscription plans and their limits."
          actions={<Button onClick={openCreate}>Create Plan</Button>}
        />

        <Card className="p-5">
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

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <span className="text-sm text-[var(--color-muted)]">Page {currentPage} of {totalPages}</span>
              <Button intent="secondary" size="sm" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          )}
        </Card>
      </div>

      {/* Create/Edit Plan Modal */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setModal(null)} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              {modal.mode === 'create' ? 'Create Plan' : 'Edit Plan'}
            </h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <div className="grid grid-cols-2 gap-4">
                <Input label="Monthly Price" type="number" value={form.monthly_price} onChange={(e) => setForm({ ...form, monthly_price: e.target.value })} />
                <Input label="Yearly Price" type="number" value={form.yearly_price} onChange={(e) => setForm({ ...form, yearly_price: e.target.value })} />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <Input label="Max Employees" type="number" value={form.max_employees} onChange={(e) => setForm({ ...form, max_employees: e.target.value })} />
                <Input label="Max OCR Docs" type="number" value={form.max_ocr_documents} onChange={(e) => setForm({ ...form, max_ocr_documents: e.target.value })} />
                <Input label="Max Storage (GB)" type="number" value={form.max_storage_gb} onChange={(e) => setForm({ ...form, max_storage_gb: e.target.value })} />
              </div>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                  <option value="ARCHIVED">Archived</option>
                </select>
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={() => setModal(null)}>Cancel</Button>
              <Button onClick={handleSave} isLoading={saving}>{modal.mode === 'create' ? 'Create' : 'Save'}</Button>
            </div>
          </div>
        </div>
      )}

      {/* Old delete confirm dialog — replaced by activate/deactivate
      <ConfirmDialog
        open={!!confirm}
        title="Delete plan?"
        message={confirm ? `Are you sure you want to delete ${confirm.plan.name}?` : ''}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />
      */}

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? `${confirm.action === 'activate' ? 'Activate' : 'Deactivate'} plan?` : ''}
        message={confirm ? `Are you sure you want to ${confirm.action} ${confirm?.plan?.name}?` : ''}
        confirmLabel={confirm?.action === 'activate' ? 'Activate' : 'Deactivate'}
        intent="primary"
        onConfirm={handlePlanAction}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
