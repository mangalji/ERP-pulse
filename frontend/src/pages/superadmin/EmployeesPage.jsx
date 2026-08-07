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

const EMPTY_EMPLOYEE = {
  email: '',
  password: '',
  first_name: '',
  last_name: '',
  company_id: '',
}

export default function EmployeesPage() {
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [companies, setCompanies] = useState([])
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_EMPLOYEE)
  const [saving, setSaving] = useState(false)
  const [confirm, setConfirm] = useState(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listEmployees({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load employees')
    } finally {
      setLoading(false)
    }
  }, [search, offset])

  useEffect(() => {
    load()
  }, [load])

  const loadCompanies = async () => {
    try {
      const data = await superadminApi.listCompanies({ limit: 100 })
      setCompanies(data.results || [])
    } catch {
      setCompanies([])
    }
  }

  const openCreate = () => {
    setForm(EMPTY_EMPLOYEE)
    setCreateOpen(true)
    loadCompanies()
  }

  const handleCreate = async () => {
    setSaving(true)
    try {
      await superadminApi.createEmployee({
        ...form,
        company_id: form.company_id || undefined,
      })
      addToast('Employee created successfully')
      setCreateOpen(false)
      setOffset(0)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to create employee', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (employee) => {
    setSaving(true)
    try {
      if (employee.is_active) {
        await superadminApi.deactivateEmployee(employee.id)
        addToast('Employee deactivated')
      } else {
        await superadminApi.activateEmployee(employee.id)
        addToast('Employee activated')
      }
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    {
      key: 'full_name',
      header: 'Name',
      render: (row) => (
        <div>
          <p className="font-medium text-[var(--color-ink)]">{row.full_name || `${row.first_name} ${row.last_name}`.trim() || '—'}</p>
          <p className="text-xs text-[var(--color-muted)]">{row.email}</p>
        </div>
      ),
    },
    {
      key: 'company_name',
      header: 'Company',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.company_name || 'AGSuite'}</span>,
    },
    { key: 'designation', header: 'Designation', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.designation || '—'}</span> },
    { key: 'department', header: 'Department', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.department || '—'}</span> },
    {
      key: 'is_active',
      header: 'Status',
      render: (row) => <StatusBadge status={row.is_active ? 'ACTIVE' : 'INACTIVE'} />,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          {row.is_active ? (
            <button
              onClick={() => setConfirm({ employee: row, action: 'deactivate' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
            >
              Deactivate
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ employee: row, action: 'activate' })}
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
    <AdminLayout title="Employees" breadcrumb="Employees">
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
          title="Employees"
          subtitle="Manage AGSuite and client employees."
          actions={<Button onClick={openCreate}>Create Employee</Button>}
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setOffset(0) }} placeholder="Search employees..." />
            <span className="text-xs text-[var(--color-muted)]">{count} employee{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No employees found"
            emptyDescription="Try adjusting your search or create a new employee."
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

      {/* Create Employee Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setCreateOpen(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Create Employee</h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              <Input label="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <div className="grid grid-cols-2 gap-4">
                <Input label="First Name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
                <Input label="Last Name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
              </div>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Company</span>
                <select
                  value={form.company_id}
                  onChange={(e) => setForm({ ...form, company_id: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">AGSuite (no company)</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
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

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? `${confirm.action === 'activate' ? 'Activate' : 'Deactivate'} employee?` : ''}
        message={confirm ? `Are you sure you want to ${confirm.action} ${confirm.employee.email}?` : ''}
        confirmLabel={confirm?.action === 'activate' ? 'Activate' : 'Deactivate'}
        intent={confirm?.action === 'deactivate' ? 'primary' : 'primary'}
        onConfirm={() => confirm && toggleActive(confirm.employee)}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
