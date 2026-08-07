import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

const PAGE_SIZE = 10

const EMPTY_FORM = {
  name: '',
  code: '',
  contact_email: '',
  contact_phone: '',
  country: '',
  status: 'TRIAL',
  admin_first_name: '',
  admin_last_name: '',
  admin_email: '',
}

export default function CompaniesPage() {
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')

  const [selected, setSelected] = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listCompanies({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
        ordering: `${sortOrder === 'desc' ? '-' : ''}${sortBy}`,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load companies')
    } finally {
      setLoading(false)
    }
  }, [search, offset, sortBy, sortOrder])

  useEffect(() => {
    load()
  }, [load])

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
    setOffset(0)
  }

  const handleSearch = (value) => {
    setSearch(value)
    setOffset(0)
  }

  const openDrawer = (company) => {
    setSelected(company)
    setDrawerOpen(true)
  }

  const handleCreate = async () => {
    setSaving(true)
    try {
      const created = await superadminApi.createCompany(form)
      addToast('Company created successfully')
      setCreateOpen(false)
      setForm(EMPTY_FORM)
      setOffset(0)
      load()
      setSelected(created)
      setDrawerOpen(true)
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to create company', 'error')
    } finally {
      setSaving(false)
    }
  }

  const runAction = async (action, company) => {
    setConfirm(null)
    try {
      await action(company)
      addToast('Action completed successfully')
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <button onClick={() => openDrawer(row)} className="font-medium text-[var(--color-primary)] hover:underline">
          {row.name}
        </button>
      ),
    },
    { key: 'code', header: 'Code' },
    { key: 'contact_email', header: 'Email', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.contact_email || '—'}</span> },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: 'user_count',
      header: 'Users',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.user_count ?? 0}</span>,
    },
    {
      key: 'module_count',
      header: 'Modules',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.module_count ?? 0}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button onClick={() => openDrawer(row)} className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
            View
          </button>
          {row.status === 'SUSPENDED' ? (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.activateCompany(row.id), company: row, label: 'Activate' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Activate
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.suspendCompany(row.id), company: row, label: 'Suspend' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
            >
              Suspend
            </button>
          )}
          {row.is_deleted ? (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.restoreCompany(row.id), company: row, label: 'Restore' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Restore
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.softDeleteCompany(row.id), company: row, label: 'Delete' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
            >
              Delete
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <AdminLayout title="Companies" breadcrumb="Companies">
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Companies"
          subtitle="Manage all client companies across the platform."
          actions={
            <Button onClick={() => setCreateOpen(true)}>Create Company</Button>
          }
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={handleSearch} placeholder="Search companies..." />
            <span className="text-xs text-[var(--color-muted)]">{count} result{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No companies found"
            emptyDescription="Try adjusting your search or create a new company."
          />

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <span className="text-sm text-[var(--color-muted)]">
                Page {currentPage} of {totalPages}
              </span>
              <Button intent="secondary" size="sm" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          )}
        </Card>

        {/* Sort hint */}
        <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
          <button onClick={() => toggleSort('name')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by name
          </button>
          <span>·</span>
          <button onClick={() => toggleSort('created_at')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by created
          </button>
          <span>·</span>
          <button onClick={() => toggleSort('status')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by status
          </button>
        </div>
      </div>

      {/* Create Company Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setCreateOpen(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Create Company</h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input label="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
              <Input label="Contact Email" type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
              <Input label="Contact Phone" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
              <Input label="Country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
              <h4 className="mt-2 text-sm font-medium text-[var(--color-ink-soft)]">Admin User</h4>
              <Input label="First Name" value={form.admin_first_name} onChange={(e) => setForm({ ...form, admin_first_name: e.target.value })} />
              <Input label="Last Name" value={form.admin_last_name} onChange={(e) => setForm({ ...form, admin_last_name: e.target.value })} />
              <Input label="Admin Email" type="email" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} required />
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="TRIAL">Trial</option>
                  <option value="ACTIVE">Active</option>
                  <option value="SUSPENDED">Suspended</option>
                </select>
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} isLoading={saving}>Create</Button>
            </div>
          </div>
        </div>
      )}

      {/* Company Detail Drawer */}
      {drawerOpen && selected && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto border-l border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <div className="mb-6 flex items-center justify-between">
              <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                {selected.name}
              </h3>
              <button onClick={() => setDrawerOpen(false)} className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex flex-col gap-4">
              <InfoCard
                title="Details"
                items={[
                  { label: 'Name', value: selected.name },
                  { label: 'Code', value: selected.code },
                  { label: 'Status', value: <StatusBadge status={selected.status} /> },
                  { label: 'Contact Email', value: selected.contact_email },
                  { label: 'Contact Phone', value: selected.contact_phone },
                  { label: 'Country', value: selected.country },
                ]}
              />
               <InfoCard
                 title="Usage"
                 items={[
                   { label: 'Users', value: selected.user_count ?? 0 },
                   { label: 'Modules', value: selected.module_count ?? 0 },
                   { label: 'Created', value: selected.created_at ? new Date(selected.created_at).toLocaleDateString() : '—' },
                 ]}
               />
               <Button
                 size="sm"
                 intent="secondary"
                 onClick={() => navigate(`/admin/companies/${selected.id}/subscription`)}
               >
                 View Subscription
               </Button>
             </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? `${confirm.label} company?` : ''}
        message={confirm ? `Are you sure you want to ${confirm.label.toLowerCase()} ${confirm.company.name}?` : ''}
        confirmLabel={confirm?.label}
        intent={confirm?.label === 'Delete' || confirm?.label === 'Suspend' ? 'primary' : 'primary'}
        onConfirm={() => confirm && runAction(confirm.action, confirm.company)}
        onCancel={() => setConfirm(null)}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
