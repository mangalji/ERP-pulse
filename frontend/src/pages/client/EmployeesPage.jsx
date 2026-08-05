import { useState, useCallback, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { clientApi } from '../../services/client.js'

export default function EmployeesPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '', password: '' })

  const loadEmployees = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.listEmployees({ limit: 100 })
      const list = data?.results ?? data ?? []
      // The backend already scopes to request.user.company. No client-side
      // filtering is performed here.
      setEmployees(list)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load employees')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadEmployees()
  }, [loadEmployees])

  const filtered = employees.filter((e) =>
    `${e.first_name || ''} ${e.last_name || ''} ${e.email || ''}`.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  const handleCreate = async (event) => {
    event.preventDefault()
    setCreating(true)
    try {
// company_id is intentionally NOT sent — the backend scopes the
      // new employee to request.user.company.
      await clientApi.createEmployee({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
      })
      addToast('Employee created successfully', 'success')
      setShowCreate(false)
      setForm({ email: '', first_name: '', last_name: '', password: '' })
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

  return (
    <ClientLayout title="Employees" breadcrumb="Employees">
      <div className="flex flex-col gap-6">
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
              Create Employee
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
                id="empPassword"
                label="Password"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
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
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" isLoading={creating}>
                  Create Employee
                </Button>
                <Button intent="ghost" onClick={() => setShowCreate(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
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
                    <th className="pb-2 pr-4 font-medium">Designation</th>
                    <th className="pb-2 pr-4 font-medium">Department</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
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
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.designation || '—'}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{employee.department || '—'}</td>
                      <td className="py-3 pr-4">
                        <Badge tone={employee.is_active ? 'positive' : 'neutral'}>
                          {employee.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-3">
                        <Button size="sm" intent="secondary" onClick={() => handleToggleActive(employee)}>
                          {employee.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
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
