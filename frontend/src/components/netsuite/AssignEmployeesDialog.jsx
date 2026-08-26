import { useState, useEffect } from 'react'
import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import Toast, { useToast } from '../ui/Toast.jsx'
import { netsuiteApi } from '../../services/netsuite.js'

export default function AssignEmployeesDialog({ connectionId, employees=[], assignedEmployees=[], onClose, onAssigned }) {
  const { toasts, addToast, removeToast } = useToast()
  const [selected, setSelected] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  function getAssignedEmployeeId(item) {
  return (
    item?.employee_id ||
    item?.employee?.id ||
    item?.id
  )
}

const assignedIds = new Set(
  assignedEmployees
    .map(getAssignedEmployeeId)
    .filter(Boolean),
)

  const toggle = (empId) => {
    if (assignedIds.has(empId)){
      return
    }
    setSelected((prev) =>
      prev.includes(empId) ? prev.filter((id) => id !== empId) : [...prev, empId]
    )
  }

  const handleAssign = async () => {

    if (selected.length===0){
      addToast(
        'Select at least one employee',
      'error',
      )
      return
    }
    setLoading(true)
    try {
      await Promise.all(selected.map((empId) => netsuiteApi.assignEmployee(connectionId, empId)))
      addToast('Employees assigned successfully', 'success')
      onAssigned?.()
      onClose?.()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to assign employees', 'error')
    } finally {
      setLoading(false)
    }
  }

  const filtered = employees.filter((e) =>
    (e.email || '').toLowerCase().includes(search.toLowerCase()) ||
    (e.first_name || '').toLowerCase().includes(search.toLowerCase()) ||
    (e.last_name || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <Card className="relative w-full max-w-lg p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Assign Employees</h3>
          <button onClick={onClose} className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <Input placeholder="Search employees..." value={search} onChange={(e) => setSearch(e.target.value)} className="mb-4" />
        <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {filtered.length === 0 && <p className="text-sm text-[var(--color-muted)]">No employees found.</p>}
          {filtered.map((emp) => {
            const empId = emp.id
            const isSelected = selected.includes(empId)
            return (
              <label key={empId} className={`flex items-center gap-3 rounded-lg border p-3 ${isSelected ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]' : 'border-[var(--color-border)]'}`}>
                <input type="checkbox" checked={isSelected} onChange={() => toggle(empId)} className="rounded border-[var(--color-border)]" />
                <div>
                  <p className="text-sm font-medium text-[var(--color-ink)]">{emp.first_name} {emp.last_name}</p>
                  <p className="text-xs text-[var(--color-muted)]">{emp.email}</p>
                </div>
              </label>
            )
          })}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button intent="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleAssign} isLoading={loading}>Assign Selected</Button>
        </div>
        <Toast toasts={toasts} removeToast={removeToast} />
      </Card>
    </div>
  )
}
