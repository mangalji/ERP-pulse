import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import { superadminApi } from '../../services/superadmin.js'
import { invitationApi } from '../../services/invitations.js'
import {COUNTRY_OPTIONS, NAME_MAX_LENGTH, EMAIL_MAX_LENGTH, getCountryRule, validateEmail, validateName, validatePhone} from '../../utils/formValidation.js'

const PAGE_SIZE = 10

const EMPTY_EMPLOYEE = {
  first_name: '',
  last_name: '',
  email: '',
  mobile_number: '',
  country: 'IN',
  phone_country_code: '+91',
  role:'employee',
  company_id: '',
  designation: '',
  department: '',
}

export default function EmployeesPage() {

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [companies, setCompanies] = useState([])
  const [departments, setDepartments] = useState([])
  const [editingDepartments, setEditingDepartments] = useState(false)
  const [departmentName, setDepartmentName] = useState('')
  const [departmentsSaving, setDepartmentsSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_EMPLOYEE)
  const [touched, setTouched] = useState({})
  const [fieldErrors, setFieldErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [confirm, setConfirm] = useState(null)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const companyId = searchParams.get('company_id')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listEmployees({
        search: search || undefined,
        company_id: companyId || undefined,
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
  }, [search, offset, companyId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    let cancelled = false
    if (!createOpen || !form.company_id) {
      setDepartments([])
      return () => { cancelled = true }
    }
    superadminApi.listCompanyDepartments(form.company_id)
      .then((data) => {
        if (!cancelled) setDepartments(data || [])
      })
      .catch(() => {
        if (!cancelled) setDepartments([])
      })
    return () => { cancelled = true }
  }, [createOpen, form.company_id])

  const loadCompanies = async () => {
    try {
      const data = await superadminApi.listCompanies({ limit: 100 })
      setCompanies(data.results || [])
    } catch {
      setCompanies([])
    }
  }

  const refreshDepartments = async () => {
    if (!form.company_id) return
    try {
      const data = await superadminApi.listCompanyDepartments(form.company_id)
      setDepartments(data.results || data || [])
    } catch (err) {
      setDepartments([])
      alert(err.payload?.detail || err.payload?.message || err.message || 'Failed to load departments')
    }
  }

  const addDepartment = async () => {
    const name = departmentName.trim()
    if (!name || !form.company_id) return
    setDepartmentsSaving(true)
    try {
      await superadminApi.createCompanyDepartment(form.company_id, name)
      setDepartmentName('')
      await refreshDepartments()
    } catch (err) {
      alert(err.payload?.detail || err.payload?.message || err.message || 'Failed to add department')
    } finally {
      setDepartmentsSaving(false)
    }
  }

  const removeDepartment = async (department) => {
    if (!form.company_id || !window.confirm(`Remove ${department.name}?`)) return
    setDepartmentsSaving(true)
    try {
      await superadminApi.deleteCompanyDepartment(form.company_id, department.id)
      if (form.department === department.name) updateField('department', '')
      await refreshDepartments()
    } catch (err) {
      alert(err.payload?.detail || err.payload?.message || err.message || 'Failed to remove department')
    } finally {
      setDepartmentsSaving(false)
    }
  }

  const handleCountryChange = (country) => {
  const selected = COUNTRY_OPTIONS.find((item) => item.value === country)

  setForm((prev) => ({
    ...prev,
    country,
    phone_country_code: selected?.dialCode || '',
  }))

  const phoneError = validatePhone(form.mobile_number, country)

  setTouched((prev) => ({
    ...prev,
    country: true,
    mobile_number: true,
  }))

  setFieldErrors((prev) => ({
    ...prev,
    country: country ? '' : 'Please select a country.',
    mobile_number: phoneError,
  }))
}

  const openCreate = () => {
    setForm(EMPTY_EMPLOYEE)
    setFormError('')
    setCreateOpen(true)
    loadCompanies()
  }

  const updateField = (field, value) => {
  setForm((prev) => ({
    ...prev,
    [field]: value,
  }))

  setTouched((prev) => ({
    ...prev,
    [field]: true,
  }))

  let error = ''

  if (field === 'email') {
    error = validateEmail(value)
  }

  if (field === 'first_name') {
    error = validateName(value, 'First Name')
  }

  if (field === 'last_name') {
    error = validateName(value, 'Last Name', false)
  }

  if (field === 'mobile_number') {
    error = validatePhone(value, form.country)
  }

  setFieldErrors((prev) => ({
    ...prev,
    [field]: error,
  }))
}

const isFormValid = () => {
  const errors = {
    email: validateEmail(form.email),
    first_name: validateName(form.first_name, 'First Name'),
    last_name: validateName(form.last_name, 'Last Name', false),
    mobile_number: validatePhone(form.mobile_number, form.country),
    country: form.country ? '' : 'Please select a country.',
    company_id: form.company_id ? '' : 'Please select a company.',
    role: ['employee', 'company_admin'].includes(form.role)
      ? ''
      : 'Please select a role.',
    designation: form.designation.trim() ? '' : 'Designation is required.',
    department: form.department.trim() ? '' : 'Department is required.',
  }

  setTouched({
    email: true,
    first_name: true,
    last_name: true,
    mobile_number: true,
    country: true,
    company_id: true,
    role: true,
    designation: true,
    department: true,
  })

  setFieldErrors(errors)

  return !Object.values(errors).some(Boolean)
}

  const verifyEmailOnBlur = async () => {
    const email = form.email.trim()
    const localError = validateEmail(email)
    if (localError) return

    try {
      const result = await invitationApi.verifyEmail(email)
      if (result.should_block) {
        setTouched((prev) => ({ ...prev, email: true }))
        setFieldErrors((prev) => ({
          ...prev,
          email: 'Please enter a valid, active email address.',
        }))
      }
    } catch {
      // Creation also verifies server-side; a transient lookup failure must
      // not make the form unusable.
    }
  }

  const handleCreate = async () => {
    setFormError('')

    if (!isFormValid()) {
  return
}

    setSaving(true)
    try {
      await superadminApi.createEmployee({
        ...form,
        company_id: form.company_id || undefined,
        role: form.role,
      })
      alert('Invitation sent successfully')
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
        alert('Employee deactivated')
      } else {
        await superadminApi.activateEmployee(employee.id)
        alert('Employee activated')
      }
      load()
    } catch (err) {
      alert(err.payload?.message || err.message || 'Action failed')
    } finally {
      setSaving(false)
    }
  }

  const handleResendInvitation = async (employee) => {
    setSaving(true)
  
    try {
      await superadminApi.resendEmployeeInvitation(employee.id)
  
      alert('Invitation resent successfully')
      load()
    } catch (err) {
      alert(
        err.payload?.message ||
        err.payload?.detail ||
        err.message ||
        'Failed to resend invitation',
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
    {
  key: 'company_status',
  header: 'Company Status',
  render: (row) => (
    row.company_status ? (
      <StatusBadge status={row.company_status} />
    ) : (
      <span className="text-[var(--color-muted)]">—</span>
    )
  ),
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

  const isCompanySuspended =
  row.company_status === 'SUSPENDED'

if (isCompanySuspended) {
  return (
    <span className="rounded-md bg-[var(--color-netsuite-soft)] px-2 py-1 text-xs font-medium text-[var(--color-netsuite)]">
      Company Suspended
    </span>
  )
}

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
            <div className="relative w-full max-w-3xl max-h-[calc(100vh-80px)] overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Create User</h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label={<><span className="text-red-600">*</span> Email</>} type="email" required maxLength={EMAIL_MAX_LENGTH} value={form.email} onChange={(e) => updateField('email', e.target.value)} onBlur={verifyEmailOnBlur} />
                {touched.email && (
                  <p className={`text-xs ${fieldErrors.email ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.email || '✓ Valid email address.'}
                  </p>
                )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <Input
                    label={<><span className="text-red-600">*</span> First Name</>}
                    required
                    maxLength={NAME_MAX_LENGTH}
                    value={form.first_name}
                    onChange={(e) => updateField('first_name', e.target.value)}
                  />
                  {touched.first_name && (
                    <p className={`mt-1 text-xs ${fieldErrors.first_name ? 'text-red-600' : 'text-green-600'}`}>
                      {fieldErrors.first_name || '✓ Valid first name.'}
                    </p>
                  )}
                </div>
                <div>
                  <Input
                    label="Last Name"
                    maxLength={NAME_MAX_LENGTH}
                    value={form.last_name}
                    onChange={(e) => updateField('last_name', e.target.value)}
                  />
                  {touched.last_name && (
                    <p className={`mt-1 text-xs ${fieldErrors.last_name ? 'text-red-600' : 'text-green-600'}`}>
                      {fieldErrors.last_name || '✓ Valid last name.'}
                    </p>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                    <span className="text-red-600">*</span> Country
                  </span>
                    
                  <select
                    value={form.country}
                    onChange={(e) => handleCountryChange(e.target.value)}
                    className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  >
                    <option value="">Select country</option>
                    
                    {COUNTRY_OPTIONS.map((country) => (
                      <option key={country.value} value={country.value}>
                        {country.label} ({country.dialCode})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="grid grid-cols-[100px_1fr] gap-2">
                <Input
                  label="Code"
                  value={form.phone_country_code}
                  readOnly
                  className="bg-[var(--color-canvas)]"
                />
                <Input
                  label={<><span className="text-red-600">*</span> Mobile Number</>}
                  required
                  type="tel"
                  maxLength={getCountryRule(form.country)?.maxDigits || 15}
                  value={form.mobile_number}
                  onChange={(e) =>
                    updateField(
                      'mobile_number',
                      e.target.value.replace(/\D/g, ''),
                    )
                  }
                />
                {touched.mobile_number && (
                  <p className={`text-xs ${fieldErrors.mobile_number ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.mobile_number || '✓ Valid mobile number.'}
                  </p>
                )}
              </div>
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-[var(--color-ink-soft)]"><span className="text-red-600">*</span> Company</span>
                  <select
                  value={form.company_id}
                  onChange={(e) => {
                    setEditingDepartments(false)
                    setForm((prev) => ({ ...prev, company_id: e.target.value, department: '' }))
                  }}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  >
                    <option value="">Select company</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]"><span className="text-red-600">*</span> Role</span>
                <select
                  required
                  value={form.role}
                  onChange={(e) => updateField('role', e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="employee">Employee</option>
                  <option value="company_admin">Company Admin</option>
                </select>
              </label>
              <Input label={<><span className="text-red-600">*</span> Designation</>} required maxLength={150} value={form.designation} onChange={(e) => updateField('designation', e.target.value)} />
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
                <label className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <span className="flex items-center justify-between text-sm font-medium text-[var(--color-ink-soft)]"><span><span className="text-red-600">*</span> Department</span><button type="button" disabled={!form.company_id} onClick={() => setEditingDepartments((value) => !value)} className="text-[var(--color-primary)] underline disabled:cursor-not-allowed disabled:opacity-50">Edit</button></span>
                  <select required value={form.department} onChange={(e) => updateField('department', e.target.value)} className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]">
                    <option value="">Select department</option>
                    {departments.map((department) => <option key={department.id || department.name} value={department.name}>{department.name}</option>)}
                  </select>
                </label>
                {editingDepartments && form.company_id && (
                  <div className="w-full shrink-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-4 lg:w-80">
                    <div className="mb-3 flex items-center justify-between"><strong>Edit departments</strong><button type="button" onClick={() => setEditingDepartments(false)} aria-label="Close department editor">×</button></div>
                    <div className="mb-3 flex gap-2"><input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDepartment() } }} placeholder="New department" maxLength={150} className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm" /><Button type="button" size="sm" isLoading={departmentsSaving} onClick={addDepartment}>Add</Button></div>
                    <div className="max-h-44 space-y-1 overflow-y-auto">{departments.map((department) => <div key={department.id || department.name} className="flex items-center justify-between rounded bg-[var(--color-surface)] px-2 py-1 text-sm"><span>{department.name}</span><button type="button" disabled={departmentsSaving} onClick={() => removeDepartment(department)} className="text-red-600 disabled:opacity-50">Remove</button></div>)}</div>
                  </div>
                )}
              </div>
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
            ? confirm.action === 'resend'
                ? 'Resend Invitation?'
              : confirm.action === 'activate'
                ? 'Activate employee?'
                : 'Deactivate employee?'
            : ''
        }
        message={
          confirm
            ? confirm.action === 'resend'
                ? `Resend the invitation to ${confirm.employee.email}?`
                : `Are you sure you want to ${confirm.action} ${confirm.employee.email}?`
            : ''
        }
        confirmLabel={
          confirm?.action === 'resend'
              ? 'Resend Invitation'
            : confirm?.action === 'activate'
              ? 'Activate'
              : 'Deactivate'
        }
        intent={confirm?.action === 'deactivate' ? 'primary' : 'primary'}
        onConfirm={() => {
          if (!confirm) return 
          if (confirm.action === 'resend'){
            handleResendInvitation(confirm.employee)
          } else {
            toggleActive(confirm.employee)
          }
          setConfirm(null)
        }}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

    </AdminLayout>
  )

}
