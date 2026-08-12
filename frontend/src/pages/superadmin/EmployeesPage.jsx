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
  first_name: '',
  last_name: '',
  email: '',
  role:'admin',
  // password: '',
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
  const [formError, setFormError] = useState('')
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
    setFormError('')
    setCreateOpen(true)
    loadCompanies()
  }

  const handleCreate = async () => {
    setFormError('')
    const email = form.email.trim()

    if (!email){
      setFormError('Email is required.')
      return
    }

    if (email.length > 40){
      setFormError('Email must not exceed 40 characters.')
      return 
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setFormError('Please enter a valid email address.')
      return
    }

    if (!form.first_name.trim()) {
    setFormError('First Name is required.')
    return
  }

  if (!form.last_name.trim()) {
    setFormError('Last Name is required.')
    return
  }

  if (!form.company_id) {
    setFormError('Please select a company.')
    return
  }

  if (!form.role) {
    setFormError('Please select a role.')
    return
  }

    setSaving(true)
    try {
      await superadminApi.createEmployee({
        ...form,
        company_id: form.company_id || undefined,
        role: form.role,
      })
      addToast('Invitation sent successfully')
      setCreateOpen(false)
      setForm(EMPTY_EMPLOYEE)
      setFormError('')
      setOffset(0)
      load()
    } catch (err) {
      const message = 
        err.payload?.message || 
        err.payload?.detail ||
        err.message || 
        'Failed to send Invitation.'

      // addToast(err.payload?.message || err.message || 'Failed to create user', 'error')
      setFormError(message)
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

  const handleToggleAdmin = async (employee) => {
    setSaving(true)
    try {
      await superadminApi.updateEmployee(employee.id, { is_staff: !employee.is_staff })
      addToast(employee.is_staff ? 'Admin privileges revoked' : 'Promoted to admin')
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleResendInvitation = async (employee) => {
    setSaving(true)
  
    try {
      await superadminApi.resendEmployeeInvitation(employee.id)
  
      addToast('Invitation resent successfully')
      load()
    } catch (err) {
      addToast(
        err.payload?.message ||
        err.payload?.detail ||
        err.message ||
        'Failed to resend invitation',
        'error'
      )
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
      key: 'role',
      header: 'ROLE',
      render: (row) => (
        <StatusBadge status={row.role || (row.is_staff ? 'ADMIN' : 'EMPLOYEE')} />
      ),
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (row) => {
        const status = row.invitation_status || (
          row.is_active ? 'ACTIVE' : 'INACTIVE'
          )
        return <StatusBadge status={status} />
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => {
  const invitationStatus = row.invitation_status?.toUpperCase()
  const isPending =
    invitationStatus === 'PENDING' ||
    invitationStatus === 'INVITATION_PENDING'

  const isExpired =
    invitationStatus === 'EXPIRED' ||
    invitationStatus === 'INVITATION_EXPIRED'

  if (isPending || isExpired) {
    return (
      <div className="flex flex-wrap items-center gap-1">
        <button
          onClick={() =>
            setConfirm({
              employee: row,
              action: 'resend',
            })
          }
          className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
        >
          Resend Invitation
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1">
      {!row.is_staff && (
        <button
          onClick={() =>
            setConfirm({
              employee: row,
              action: 'promote',
            })
          }
          className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
        >
          Promote Admin
        </button>
      )}

      {row.is_active ? (
        <button
          onClick={() =>
            setConfirm({
              employee: row,
              action: 'deactivate',
            })
          }
          className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
        >
          Deactivate
        </button>
      ) : (
        <button
          onClick={() =>
            setConfirm({
              employee: row,
              action: 'activate',
            })
          }
          className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
        >
          Activate
        </button>
      )}
    </div>
  )
},
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
          title="Users"
          subtitle="Manage AGSuite and client users."
          actions={<Button onClick={openCreate}>Create User</Button>}
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setOffset(0) }} placeholder="Search users..." />
            <span className="text-xs text-[var(--color-muted)]">{count} user{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No users found"
            emptyDescription="Try adjusting your search or create a new user."
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
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Create User</h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Email" type="email" value={form.email} onChange={(e) => {setForm({ ...form, email: e.target.value }); setFormError('');}} />
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
                    <option value="">AGSuite Internal User</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                Role
                </span>

                <select value={form.role} onChange={(e) => setForm({...form, role: e.target.value})}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  >
                  <option value="employee">
                      Employee
                  </option>
                
                  <option value="admin">
                      Company Admin
                  </option>
                
                </select>
              </label>
              {formError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
                  {formError}
                </div>
                )}
              <div className="mt-6 flex justify-end gap-2">
                <Button intent="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} isLoading={saving}>Send Invitation</Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirm}
        title={
          confirm
            ? confirm.action === 'promote'
              ? 'Promote to Admin?'
              : confirm.action === 'resend'
                ? 'Resend Invitation?'
              : confirm.action === 'activate'
                ? 'Activate employee?'
                : 'Deactivate employee?'
            : ''
        }
        message={
          confirm
            ? confirm.action === 'promote'
              ? `Are you sure you want to promote ${confirm.employee.email} to Company Admin?`
              // : `Are you sure you want to ${confirm.action} ${confirm.employee.email}?`
              : confirm.action === 'resend'
                ? `Resend the invitation to ${confirm.employee.email}?`
                : `Are you sure you want to ${confirm.action} ${confirm.employee.email}?`
            : ''
        }
        confirmLabel={
          confirm?.action === 'promote'
            ? 'Promote Admin'
            : confirm?.action === 'resend'
              ? 'Resend Invitation'
            : confirm?.action === 'activate'
              ? 'Activate'
              : 'Deactivate'
        }
        intent={confirm?.action === 'deactivate' ? 'primary' : 'primary'}
        onConfirm={() => {
          if (!confirm) return 
          if (confirm.action==='promote'){
            handleToggleAdmin(confirm.employee)
          } else if (confirm.action === 'resend'){
            handleResendInvitation(confirm.employee)
          } else {
            toggleActive(confirm.employee)
          }
          setConfirm(null)
        }}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )

}