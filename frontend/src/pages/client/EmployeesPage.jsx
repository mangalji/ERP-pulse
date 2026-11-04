import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import { clientApi } from '../../services/client.js'
import { invitationApi } from '../../services/invitations.js'
import { useAuth } from '../../contexts/AuthContext.jsx'
import {
  COUNTRY_OPTIONS,
  NAME_MAX_LENGTH,
  EMAIL_MAX_LENGTH,
  getCountryRule,
  validateEmail,
  validateName,
  validatePhone,
  PHONE_MAX_DIGITS,
} from '../../utils/formValidation.js'

export default function EmployeesPage() {
  const { user } = useAuth()
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [roles, setRoles] = useState([])
  const [form, setForm] = useState({email: '', first_name: '', last_name: '', mobile_number: '', country: 'IN', phone_country_code: '+91', role_id: '', designation: '', department: ''})
  const [departments, setDepartments] = useState([])
  const [departmentName, setDepartmentName] = useState('')
  const [editingDepartments, setEditingDepartments] = useState(false)
  const [touched, setTouched] = useState({})
  const [fieldErrors, setFieldErrors] = useState({})
  const [editingEmployee, setEditingEmployee] = useState(null)
  const [editing, setEditing] = useState(false)
  const [viewEmployee, setViewEmployee] = useState(null)
  const navigate = useNavigate()

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

  if (field === 'email') error = validateEmail(value)
  if (field === 'first_name') error = validateName(value, 'First Name')
  if (field === 'last_name') error = validateName(value, 'Last Name', false)
  if (field === 'mobile_number') error = validatePhone(value, form.country)
  if (field === 'designation') error = value.trim() ? '' : 'Designation is required.'
  if (field === 'department') error = value ? '' : 'Department is required.'
  if (field === 'role_id') error = value ? '' : 'Role is required.'

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
    country: form.country ? '' : 'Please select a country.',
    mobile_number: validatePhone(form.mobile_number, form.country),
    role_id: form.role_id ? '' : 'Role is required.',
    designation: form.designation.trim() ? '' : 'Designation is required.',
    department: form.department ? '' : 'Department is required.',
  }

  setTouched({
    email: true,
    first_name: true,
    last_name: true,
    country: true,
    mobile_number: true,
    role_id: true,
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
      // Final server-side verification on submit remains authoritative.
    }
  }
function hasEmployeePassword(employee) {
  if (typeof employee?.has_password === 'boolean') {
    return employee.has_password
  }

  return String(employee?.invitation_status || '').trim().toLowerCase() === 'accepted'
}

  const loadEmployees = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.listEmployees({ limit: 100 })
      const list = data?.results ?? data ?? []
      setEmployees(list)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load employees')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadRoles = useCallback(async () => {
    try {
      const data = await clientApi.listRoles()
      setRoles(data.results || data || [])
    } catch {
      setRoles([])
    }
  }, [])

  const loadDepartments = useCallback(async () => {
    try {
      const data = await clientApi.listDepartments()
      setDepartments(data.results || data || [])
    } catch {
      setDepartments([])
    }
  }, [])

  useEffect(() => {
    loadEmployees()
    loadRoles()
    loadDepartments()
  }, [loadEmployees, loadRoles, loadDepartments])

  const filtered = employees.filter((e) =>
    `${e.first_name || ''} ${e.last_name || ''} ${e.email || ''}`.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  const getRoleName = (employee) => {
    const roleIds = employee.roles || []
    const roleNames = roleIds.map(r => {
      const role = roles.find(rr => String(rr.id) === String(r.role_id))
      return role ? role.name : ''
    })
    return roleNames.filter(Boolean).join(', ') || '—'
  }

  const getPrimaryRoleName = (employee) => {
    const assignedRole = employee.roles?.[0]
    if (!assignedRole) return ''
    return (
      assignedRole.role__name ||
      roles.find((role) => String(role.id) === String(assignedRole.role_id))?.name ||
      ''
    )
  }

  const handleRoleTransition = async (employee, roleName) => {
    if (String(employee.id) === String(user?.id)) {
      alert('You cannot change your own role.')
      return
    }

    const role = roles.find(
      (item) => String(item.name).trim().toLowerCase() === roleName.toLowerCase(),
    )
    if (!role) {
      alert(`${roleName} role is not configured.`)
      return
    }

    try {
      await clientApi.assignEmployeeRole(employee.id, role.id)
      alert(
        roleName === 'Company Admin'
          ? 'Employee promoted to Company Admin.'
          : 'Company Admin demoted to Employee.',
      )
      loadEmployees()
    } catch (err) {
      alert(err.payload?.detail || err.payload?.message || err.message || 'Role update failed')
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

  const addDepartment = async () => {
    const name = departmentName.trim()
    if (!name) return
    try {
      await clientApi.createDepartment(name)
      setDepartmentName('')
      await loadDepartments()
    } catch (err) {
      alert(err.payload?.detail || err.payload?.message || err.message || 'Failed to add department')
    }
  }

  const removeDepartment = async (department) => {
    if (!window.confirm(`Remove ${department.name}?`)) return
    try {
      await clientApi.deleteDepartment(department.id)
      if (form.department === department.name) updateField('department', '')
      await loadDepartments()
    } catch (err) {
      alert(err.payload?.detail || err.payload?.message || err.message || 'Failed to remove department')
    }
  }

  const handleCreate = async (event) => {
    event.preventDefault()

    if (!isFormValid()) {
      return
    }

    setCreating(true)
    try {
      await clientApi.createEmployee({
        email: form.email,
        first_name: form.first_name,
        last_name: form.last_name,
        mobile_number: form.mobile_number,
        country: form.country,
        phone_country_code: form.phone_country_code,
        role_id: form.role_id,
        designation: form.designation,
        department: form.department,
      })
      alert('Employee invitation sent successfully')
      setShowCreate(false)
      setForm({email: '', first_name: '', last_name: '', mobile_number: '', country: 'IN', phone_country_code: '+91', role_id: '', designation: '', department: '', })
      loadEmployees()
    } catch (err) {
      alert(
        err.payload?.detail ||
        err.payload?.message ||
        err.message ||
        'Failed to create employee',
      )
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (employee) => {
    try {
      if (employee.is_active) {
        await clientApi.deactivateEmployee(employee.id)
        alert('Employee deactivated')
      } else {
        await clientApi.activateEmployee(employee.id)
        alert('Employee activated')
      }
      loadEmployees()
    } catch (err) {
      alert(err.payload?.message || err.message || 'Action failed')
    }
  }

  const handleResendInvitation = async (employee, isNewInvitation = false) => {
    try {
      await clientApi.resendEmployeeInvitation(employee.id)
      alert(
        isNewInvitation
          ? 'Invitation sent successfully'
          : 'Invitation resent successfully',
      )
      loadEmployees()
    } catch (err) {
      alert(err.payload?.message || err.message || 'Failed to resend invitation')
    }
  }

  const handleEdit = async (employee) => {
    const full = await clientApi.getEmployee(employee.id)
    const emp = full?.employee || full
    setEditingEmployee(emp)
    setForm({
      email: emp.email || '',
      first_name: emp.first_name || '',
      last_name: emp.last_name || '',
      mobile_number: emp.mobile_number || '',
      country: emp.country || 'IN',
      phone_country_code: emp.phone_country_code || '+91',
      role_id: emp.roles?.[0]?.role_id ? String(emp.roles[0].role_id) : '',
      designation: emp.designation || '',
      department: emp.department || '',
    })
    setShowCreate(false)
    setTouched({})
    setFieldErrors({})
  }

  const handleUpdate = async (event) => {
    event.preventDefault()
    if (!isFormValid()) {
  return
}
    setEditing(true)
    try {
      await clientApi.updateEmployee(editingEmployee.id, {
        first_name: form.first_name,
        last_name: form.last_name,
        mobile_number: form.mobile_number,
        country: form.country,
        phone_country_code: form.phone_country_code,
        designation: form.designation,
        department: form.department,
      })
      alert('Employee updated successfully')
      setEditingEmployee(null)
      loadEmployees()
    } catch (err) {
      alert(err.payload?.message || err.message || 'Failed to update employee')
    } finally {
      setEditing(false)
    }
  }

  const handleView = async (employee) => {
    const full = await clientApi.getEmployee(employee.id)
    const emp = full?.employee || full
    setViewEmployee(emp)
  }

  const closeView = () => setViewEmployee(null)

  return (
    <ClientLayout title="Employees" breadcrumb="Employees">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/app')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
           <span className="text-sm text-[var(--color-muted)]">Dashboard</span>
         </div>
         <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Company Employees
            </h1>
            <p className="text-sm text-[var(--color-muted)]">
              Manage the people in your company and their access to the portal.
            </p>
          </div>
           <Button intent="primary" onClick={() => setShowCreate((prev) => !prev)}>
             + Add Employee
           </Button>
        </div>

        {showCreate && (
          <Card className="p-6">
            <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Invite Employee
            </h2>
            <form onSubmit={handleCreate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                id="empEmail"
                label={<><span className="text-red-600">*</span> Email</>}
                type="email"
                required
                maxLength={EMAIL_MAX_LENGTH}
                value={form.email}
                onChange={(e) => updateField('email', e.target.value)}
                onBlur={verifyEmailOnBlur}
              />
              {touched.email && (
  <p className={`text-xs ${fieldErrors.email ? 'text-red-600' : 'text-green-600'}`}>
    {fieldErrors.email || '✓ Valid email address.'}
  </p>
)}
              <Input
                id="empFirst"
                label={<><span className="text-red-600">*</span> First name</>}
                required
                value={form.first_name}
                onChange={(e) => updateField('first_name', e.target.value)}
                maxLength={NAME_MAX_LENGTH}
              />
              {touched.first_name && (
                <p className={`text-xs ${fieldErrors.first_name ? 'text-red-600' : 'text-green-600'}`}>
                  {fieldErrors.first_name || '✓ Valid first name.'}
                </p>
              )}
              <Input
                id="empLast"
                label="Last name"
                value={form.last_name}
                onChange={(e) => updateField('last_name', e.target.value)}
                maxLength={NAME_MAX_LENGTH}
              />
              {touched.last_name && (
                <p className={`text-xs ${fieldErrors.last_name ? 'text-red-600' : 'text-green-600'}`}>
                  {fieldErrors.last_name || '✓ Valid last name.'}
                </p>
              )}
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]"><span className="text-red-600">*</span> Role</span>
                <select
                  value={form.role_id}
                  onChange={(e) => updateField('role_id', e.target.value)}
                  required
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select a role</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </label>
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

<div className="grid grid-cols-[100px_1fr] gap-2">
  <Input
    label="Code"
    value={form.phone_country_code}
    readOnly
    className="bg-[var(--color-canvas)]"
  />

  <Input
    label={<><span className="text-red-600">*</span> Mobile Number</>}
    type="tel"
    value={form.mobile_number}
    onChange={(e) =>
  updateField(
    'mobile_number',
    e.target.value.replace(/\D/g, ''),
  )
}
    required
    maxLength={PHONE_MAX_DIGITS}
  />
  {touched.mobile_number && (
  <p className={`text-xs ${fieldErrors.mobile_number ? 'text-red-600' : 'text-green-600'}`}>
    {fieldErrors.mobile_number || '✓ Valid mobile number.'}
  </p>
)}
</div>

              <Input
                id="empDesignation"
                label={<><span className="text-red-600">*</span> Designation</>}
                required
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
              <label className="relative flex flex-col gap-1.5">
                <span className="flex items-center justify-between text-sm font-medium text-[var(--color-ink-soft)]"><span><span className="text-red-600">*</span> Department</span><button type="button" onClick={() => setEditingDepartments((value) => !value)} className="text-[var(--color-primary)] underline">Edit</button></span>
                <select value={form.department} onChange={(e) => updateField('department', e.target.value)} required className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]">
                  <option value="">Select department</option>
                  {departments.map((department) => <option key={department.id} value={department.name}>{department.name}</option>)}
                </select>
                {editingDepartments && (
                  <div className="absolute left-full top-0 z-20 ml-3 w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xl">
                    <div className="mb-3 flex items-center justify-between"><strong>Edit departments</strong><button type="button" onClick={() => setEditingDepartments(false)} aria-label="Close department editor">×</button></div>
                    <div className="mb-3 flex gap-2"><input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} placeholder="New department" maxLength={150} className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm" /><Button type="button" size="sm" onClick={addDepartment}>Add</Button></div>
                    <div className="max-h-44 space-y-1 overflow-y-auto">{departments.map((department) => <div key={department.id} className="flex items-center justify-between rounded bg-[var(--color-canvas)] px-2 py-1 text-sm"><span>{department.name}</span><button type="button" onClick={() => removeDepartment(department)} className="text-red-600">Remove</button></div>)}</div>
                  </div>
                )}
              </label>
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" isLoading={creating}>
                  Send Invitation
                </Button>
                <Button type="button" intent="ghost" onClick={() => setShowCreate(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        )}

        {editingEmployee && (
          <Card className="p-6">
            <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Edit Employee
            </h2>
            <form onSubmit={handleUpdate} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Email (read-only)</label>
                <Input
                  id="editEmpEmail"
                  type="email"
                  readOnly
                  value={form.email}
                  className="bg-[var(--color-canvas)]"
                />
              </div>
              <Input
                id="editEmpFirst"
                label="First name"
                value={form.first_name}
                onChange={(e) => updateField('first_name', e.target.value)}
                maxLength={NAME_MAX_LENGTH}
              />
              {touched.first_name && (
                <p className={`text-xs ${fieldErrors.first_name ? 'text-red-600' : 'text-green-600'}`}>
                  {fieldErrors.first_name || '✓ Valid first name.'}
                </p>
              )}
              <Input
                id="editEmpLast"
                label="Last name"
                value={form.last_name}
                onChange={(e) => updateField('last_name', e.target.value)}
                maxLength={NAME_MAX_LENGTH}
              />
              {touched.last_name && (
                <p className={`text-xs ${fieldErrors.last_name ? 'text-red-600' : 'text-green-600'}`}>
                  {fieldErrors.last_name || '✓ Valid last name.'}
                </p>
              )}
              <label className="flex flex-col gap-1.5">
  <span className="text-sm font-medium text-[var(--color-ink-soft)]">
    Country
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

<div className="grid grid-cols-[100px_1fr] gap-2">
  <Input
    label="Code"
    value={form.phone_country_code}
    readOnly
    className="bg-[var(--color-canvas)]"
  />

  <Input
    label="Mobile Number"
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

              <Input
                id="editEmpDesignation"
                label={<><span className="text-red-600">*</span> Designation</>}
                required
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
              <label className="relative flex flex-col gap-1.5">
                <span className="flex items-center justify-between text-sm font-medium text-[var(--color-ink-soft)]"><span><span className="text-red-600">*</span> Department</span><button type="button" onClick={() => setEditingDepartments((value) => !value)} className="text-[var(--color-primary)] underline">Edit</button></span>
                <select value={form.department} onChange={(e) => updateField('department', e.target.value)} required className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]">
                  <option value="">Select department</option>
                  {departments.map((department) => <option key={department.id} value={department.name}>{department.name}</option>)}
                </select>
                {editingDepartments && (
                  <div className="absolute left-full top-0 z-20 ml-3 w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xl">
                    <div className="mb-3 flex items-center justify-between"><strong>Edit departments</strong><button type="button" onClick={() => setEditingDepartments(false)} aria-label="Close department editor">×</button></div>
                    <div className="mb-3 flex gap-2"><input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} placeholder="New department" maxLength={150} className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm" /><Button type="button" size="sm" onClick={addDepartment}>Add</Button></div>
                    <div className="max-h-44 space-y-1 overflow-y-auto">{departments.map((department) => <div key={department.id} className="flex items-center justify-between rounded bg-[var(--color-canvas)] px-2 py-1 text-sm"><span>{department.name}</span><button type="button" onClick={() => removeDepartment(department)} className="text-red-600">Remove</button></div>)}</div>
                  </div>
                )}
              </label>
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" isLoading={editing}>
                  Save Changes
                </Button>
                <Button type="button" intent="ghost" onClick={() => setEditingEmployee(null)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        )}

        {viewEmployee && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="w-full max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                  Employee Details
                </h2>
                <button
                  onClick={closeView}
                  className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                >
                  ✕
                </button>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Full Name</span>
                  <p className="text-sm font-medium text-[var(--color-ink)]">
                    {viewEmployee.full_name || `${viewEmployee.first_name || ''} ${viewEmployee.last_name || ''}`.trim() || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Email</span>
                  <p className="text-sm font-medium text-[var(--color-ink)]">{viewEmployee.email || '—'}</p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Designation</span>
                  <p className="text-sm text-[var(--color-ink)]">{viewEmployee.designation || '—'}</p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Department</span>
                  <p className="text-sm text-[var(--color-ink)]">{viewEmployee.department || '—'}</p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Role</span>
                  <p className="text-sm text-[var(--color-ink)]">{getRoleName(viewEmployee)}</p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Status</span>
                  <p className="text-sm text-[var(--color-ink)]">
                    <Badge tone={viewEmployee.is_active ? 'positive' : 'neutral'}>
                      {viewEmployee.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </p>
                </div>
                <div>
                  <span className="text-xs text-[var(--color-muted)]">Invitation</span>
                  <p className="text-sm text-[var(--color-ink)] capitalize">
                    {viewEmployee.invitation_status
                      ? String(viewEmployee.invitation_status).replaceAll('_', ' ')
                      : '—'}
                  </p>
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button intent="ghost" onClick={closeView}>Close</Button>
                <Button size="sm" intent="secondary" onClick={() => { closeView(); handleEdit(viewEmployee) }}>Edit</Button>
              </div>
            </div>
          </div>
        )}

        <Card className="p-6">
          <div className="mb-4">
            <input
              type="text"
              placeholder="Search employees..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full max-w-sm rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
            />
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={loadEmployees} />
          ) : filtered.length === 0 ? (
            <EmptyState
              title={employees.length === 0 ? 'No employees yet' : 'No employees match your search'}
              description={employees.length === 0 ? 'Add your first employee to get started.' : 'Try a different search.'}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                    <th className="pb-2 pr-4 font-medium">Name</th>
                    <th className="pb-2 pr-4 font-medium">Email</th>
                    <th className="pb-2 pr-4 font-medium">Role</th>
                    <th className="pb-2 pr-4 font-medium">Designation</th>
                    <th className="pb-2 pr-4 font-medium">Department</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Invitation</th>
                    <th className="pb-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((employee) => {
                    const invitationStatus = String(employee.invitation_status || '').toUpperCase()
                    const hasPassword = hasEmployeePassword(employee)
                    const isAccountActive = Boolean(employee.is_active) && hasPassword
                    const canSendInvitation =
                      !hasPassword &&
                      ['PENDING', 'EXPIRED', 'NONE'].includes(invitationStatus)
                    const isNewInvitation = invitationStatus === 'NONE'
                    const roleName = String(getPrimaryRoleName(employee)).trim().toLowerCase()
                    const roleTransition =
                      String(employee.id) === String(user?.id)
                        ? null
                        : roleName === 'employee'
                          ? {
                              target: 'Company Admin',
                              label: 'Promote to Admin',
                              className: 'text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]',
                            }
                          : roleName === 'company admin'
                            ? {
                                target: 'Employee',
                                label: 'Demote to Employee',
                                className: 'text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]',
                              }
                            : null

                    return (
                    <tr key={employee.id} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-3 pr-4 font-medium text-[var(--color-ink)]">
                        {employee.full_name || `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || '—'}
                      </td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.email}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{getRoleName(employee)}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.designation || '—'}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.department || '—'}</td>
                      <td className="py-3 pr-4">
                        <Badge tone={isAccountActive ? 'positive' : 'neutral'}>
                          {isAccountActive ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)] capitalize">
                        {employee.invitation_status
                          ? String(employee.invitation_status).replaceAll('_', ' ')
                          : '—'}
                      </td>
                      <td className="py-3">
                        {hasPassword ? (
                        <div className="flex flex-wrap items-center gap-1">
                          <button
                            onClick={() => handleView(employee)}
                            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                            title="View"
                          >
                            View
                          </button>
                          <button
                            onClick={() => handleEdit(employee)}
                            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                            title="Edit"
                          >
                            Edit
                          </button>
                          {roleTransition && (
                            <button
                              onClick={() => handleRoleTransition(employee, roleTransition.target)}
                              className={`rounded-md px-2 py-1 text-xs font-medium ${roleTransition.className}`}
                            >
                              {roleTransition.label}
                            </button>
                          )}
                          {canSendInvitation && (
                            <button
                              onClick={() => handleResendInvitation(employee)}
                              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                            >
                              Resend Invitation
                            </button>
                          )}
                          {String(employee.id) !== String(user?.id) && (
                            <Button size="sm" intent="secondary" onClick={() => handleToggleActive(employee)}>
                              {employee.is_active ? 'Deactivate' : 'Activate'}
                            </Button>
                          )}
                        </div>
                        ) : canSendInvitation ? (
                          <div className="flex flex-wrap items-center gap-1">
                            {roleTransition && (
                              <button
                                onClick={() => handleRoleTransition(employee, roleTransition.target)}
                                className={`rounded-md px-2 py-1 text-xs font-medium ${roleTransition.className}`}
                              >
                                {roleTransition.label}
                              </button>
                            )}
                            <button
                              onClick={() => handleResendInvitation(employee, isNewInvitation)}
                              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                            >
                              {isNewInvitation ? 'Send Invitation' : 'Resend Invitation'}
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap items-center gap-1">
                            {roleTransition && (
                              <button
                                onClick={() => handleRoleTransition(employee, roleTransition.target)}
                                className={`rounded-md px-2 py-1 text-xs font-medium ${roleTransition.className}`}
                              >
                                {roleTransition.label}
                              </button>
                            )}
                            <span className="text-xs text-[var(--color-muted)]">
                              Awaiting password setup
                            </span>
                          </div>
                        )}
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

    </ClientLayout>
  )
}
