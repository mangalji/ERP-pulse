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
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

export default function EmployeesPage() {
  const { toasts, addToast, removeToast } = useToast()
  const { user } = useAuth()
  const plan = user?.plan
  const employeeLimitReached = plan && plan.max_employees > 0 && (plan.employee_count || 0) >= plan.max_employees
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [roles, setRoles] = useState([])
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '', role_id: '', designation: '', department: '' })
  const [editingEmployee, setEditingEmployee] = useState(null)
  const [editing, setEditing] = useState(false)
  const [viewEmployee, setViewEmployee] = useState(null)
  const navigate = useNavigate()

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

  useEffect(() => {
    loadEmployees()
    loadRoles()
  }, [loadEmployees, loadRoles])

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

  const handleCreate = async (event) => {
    event.preventDefault()

    const email = form.email.trim()

    if (!email) {
      addToast('Email is required', 'error')
      return
    }
    if (email.length > 40) {
      addToast('Email must not exceed 40 characters.', 'error')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      addToast('Please enter a valid email address.', 'error')
      return
    }
    if (!form.first_name.trim()) {
      addToast('First name is required', 'error')
      return
    }
    if (!form.last_name.trim()) {
      addToast('Last name is required', 'error')
      return
    }
    if (!form.role_id) {
      addToast('Please select a role', 'error')
      return
    }

    setCreating(true)
    try {
      await clientApi.createEmployee({
        email: form.email,
        first_name: form.first_name,
        last_name: form.last_name,
        role_id: form.role_id ? Number(form.role_id) : undefined,
        designation: form.designation,
        department: form.department,
      })
      addToast('Employee invitation sent successfully', 'success')
      setShowCreate(false)
      setForm({ email: '', first_name: '', last_name: '', role_id: '', designation: '', department: '' })
      loadEmployees()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to create employee', 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (employee) => {
    try {
      if (employee.is_active) {
        await clientApi.deactivateEmployee(employee.id)
        addToast('Employee deactivated', 'success')
      } else {
        await clientApi.activateEmployee(employee.id)
        addToast('Employee activated', 'success')
      }
      loadEmployees()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    }
  }

  const handleResendInvitation = async (employee) => {
    try {
      await clientApi.resendEmployeeInvitation(employee.id)
      addToast('Invitation resent successfully', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to resend invitation', 'error')
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
      role_id: emp.roles?.[0]?.role_id ? String(emp.roles[0].role_id) : '',
      designation: emp.designation || '',
      department: emp.department || '',
    })
    setShowCreate(false)
  }

  const handleUpdate = async (event) => {
    event.preventDefault()
    setEditing(true)
    try {
      await clientApi.updateEmployee(editingEmployee.id, {
        first_name: form.first_name,
        last_name: form.last_name,
        role_id: form.role_id ? Number(form.role_id) : undefined,
        designation: form.designation,
        department: form.department,
      })
      addToast('Employee updated successfully', 'success')
      setEditingEmployee(null)
      loadEmployees()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to update employee', 'error')
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
         {employeeLimitReached && (
           <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/20">
             Employee limit reached ({plan.employee_count}/{plan.max_employees}).
             Please upgrade your plan to add more employees.
           </div>
         )}
         <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1">
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Company Employees
            </h1>
            <p className="text-sm text-[var(--color-muted)]">
              Manage the people in your company and their access to the portal.
            </p>
          </div>
           <Button intent="primary" onClick={() => setShowCreate((prev) => !prev)} disabled={employeeLimitReached}>
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
                label="Email"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
              <Input
                id="empFirst"
                label="First name"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
              <Input
                id="empLast"
                label="Last name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Role</span>
                <select
                  value={form.role_id}
                  onChange={(e) => setForm({ ...form, role_id: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select a role</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </label>
              <Input
                id="empDesignation"
                label="Designation"
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
              <Input
                id="empDepartment"
                label="Department"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
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
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
              <Input
                id="editEmpLast"
                label="Last name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Role</span>
                <select
                  value={form.role_id}
                  onChange={(e) => setForm({ ...form, role_id: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select a role</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>{role.name}</option>
                  ))}
                </select>
              </label>
              <Input
                id="editEmpDesignation"
                label="Designation"
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
              <Input
                id="editEmpDepartment"
                label="Department"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
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
                    <th className="pb-2 pr-4 font-medium">Department</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Invitation</th>
                    <th className="pb-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((employee) => (
                    <tr key={employee.id} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-3 pr-4 font-medium text-[var(--color-ink)]">
                        {employee.full_name || `${employee.first_name || ''} ${employee.last_name || ''}`.trim() || '—'}
                      </td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.email}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{getRoleName(employee)}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.department || '—'}</td>
                      <td className="py-3 pr-4">
                        <Badge tone={employee.is_active ? 'positive' : 'neutral'}>
                          {employee.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)] capitalize">
                        {employee.invitation_status
                          ? String(employee.invitation_status).replaceAll('_', ' ')
                          : '—'}
                      </td>
                      <td className="py-3">
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
                          {!employee.is_active && (
                            <button
                              onClick={() => handleResendInvitation(employee)}
                              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                            >
                              Resend Invitation
                            </button>
                          )}
                          <Button size="sm" intent="secondary" onClick={() => handleToggleActive(employee)}>
                            {employee.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </ClientLayout>
  )
}