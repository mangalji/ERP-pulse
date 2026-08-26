import { useState } from 'react'
import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Badge from '../ui/Badge.jsx'

export default function ConnectionCard({ connection, isCurrent = false, onUse, onTest, onAssign, onDelete, onEdit, onRemoveEmployee, employees = [] }) {
  const assignedCount = employees.length
  const [showAssigned, setShowAssigned] = useState(false)
  const [removingEmployeeId, setRemovingEmployeeId] = useState(null)

  const getEmployeeId = (item) =>
    item?.employee_id ||
    item?.employee?.id ||
    item?.id

  const getEmployeeName = (item) => {
    if (item?.employee_name) {
      return item.employee_name
    }

    if (item?.employee){
      return(
        `${item.employee.first_name || ''} ${item.employee.last_name || ''}`.trim() ||
        item.employee.email ||
        'Employee'
      )
    }
    return (
      `${item?.first_name || ''} ${item?.last_name || ''}`.trim() ||
      item?.email ||
      'Employee'
    )
  }
  const getEmployeeEmail = (item) =>
    item?.employee_email ||
    item?.employee?.email ||
    item?.email ||
    ''

    const handleRemoveEmployee = async (employeeId) => {
    if (!onRemoveEmployee || !employeeId) return

    setRemovingEmployeeId(employeeId)

    try {
      await onRemoveEmployee(
        connection.id,
        employeeId,
      )
    } finally {
      setRemovingEmployeeId(null)
    }
  }

  const handleRemove = async (employeeId) => {
    if (!employeeId || !onRemoveEmployee) return

    setRemovingEmployeeId(employeeId)

    try {
      await onRemoveEmployee(
        connection.id,
        employeeId,
      )
    } finally {
      setRemovingEmployeeId(null)
    }
  }

return (
  <>
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            {connection.client_name || 'Unnamed Connection'}
          </h3>

          <p className="mt-1 text-sm text-[var(--color-muted)]">
            {connection.netsuite_account_id} · {connection.environment}
          </p>

          <div className="mt-2 flex items-center gap-2">
            <Badge
              tone={
                connection.status === 'connected'
                  ? 'positive'
                  : connection.status === 'error'
                    ? 'negative'
                    : 'primary'
              }
            >
              {connection.status}
            </Badge>

            {connection.is_active && (
              <Badge tone="primary">
                Active
              </Badge>
            )}

            {isCurrent && (
              <Badge tone="positive">
                Currently Using
              </Badge>
            )}
          </div>

          {assignedCount > 0 && (
            <button
              type="button"
              onClick={() => setShowAssigned(true)}
              className="mt-2 text-xs font-medium text-[var(--color-primary)] hover:underline"
            >
              {assignedCount} employee
              {assignedCount !== 1 ? 's' : ''} assigned
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            intent={isCurrent ? 'secondary' : 'primary'}
            size="sm"
            disabled={isCurrent}
            onClick={() => onUse?.(connection.id)}
          >
            {isCurrent ? 'Using' : 'Use'}
          </Button>

          <Button
            intent="secondary"
            size="sm"
            onClick={() => onTest?.(connection.id)}
          >
            Test
          </Button>

          <Button
            intent="secondary"
            size="sm"
            onClick={() => onAssign?.(connection.id)}
          >
            Assign
          </Button>

          <Button
            intent="secondary"
            size="sm"
            onClick={() => setShowAssigned(true)}
          >
            Assigned ({assignedCount})
          </Button>

          <Button
            intent="secondary"
            size="sm"
            onClick={() => onEdit?.(connection)}
          >
            Edit
          </Button>

          <Button
            intent="negative"
            size="sm"
            onClick={() => onDelete?.(connection.id)}
          >
            Delete
          </Button>
        </div>
      </div>
    </Card>

    {showAssigned && (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="absolute inset-0 bg-black/40"
          onClick={() => setShowAssigned(false)}
        />

        <Card className="relative w-full max-w-lg p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Assigned Employees
              </h3>

              <p className="mt-1 text-sm text-[var(--color-muted)]">
                {connection.client_name || 'NetSuite Connection'}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowAssigned(false)}
              className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
            >
              ✕
            </button>
          </div>

          {employees.length === 0 ? (
            <p className="text-sm text-[var(--color-muted)]">
              No employees are assigned to this NetSuite account.
            </p>
          ) : (
            <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
              {employees.map((employee) => {
                const employeeId = getEmployeeId(employee)

                return (
                  <div
                    key={employeeId}
                    className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-[var(--color-ink)]">
                        {getEmployeeName(employee)}
                      </p>

                      <p className="text-xs text-[var(--color-muted)]">
                        {getEmployeeEmail(employee)}
                      </p>
                    </div>

                    <Button
                      intent="negative"
                      size="sm"
                      isLoading={
                        removingEmployeeId === employeeId
                      }
                      onClick={() =>
                        handleRemoveEmployee(employeeId)
                      }
                    >
                      Remove
                    </Button>
                  </div>
                )
              })}
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <Button
              intent="secondary"
              onClick={() => setShowAssigned(false)}
            >
              Close
            </Button>
          </div>
        </Card>
      </div>
    )}
  </>
)
}