import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Badge from '../ui/Badge.jsx'

export default function ConnectionCard({ connection, onTest, onAssign, onDelete, onEdit, employees = [] }) {
  const assignedCount = employees.length

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">{connection.client_name || 'Unnamed Connection'}</h3>
          <p className="mt-1 text-sm text-[var(--color-muted)]">{connection.netsuite_account_id} · {connection.environment}</p>
          <div className="mt-2 flex items-center gap-2">
            <Badge tone={connection.status === 'connected' ? 'positive' : connection.status === 'error' ? 'negative' : 'primary'}>
              {connection.status}
            </Badge>
            {connection.is_active && <Badge tone="primary">Active</Badge>}
          </div>
          {assignedCount > 0 && (
            <p className="mt-2 text-xs text-[var(--color-muted)]">{assignedCount} employee{assignedCount !== 1 ? 's' : ''} assigned</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button intent="secondary" size="sm" onClick={() => onTest?.(connection.id)}>Test</Button>
          <Button intent="secondary" size="sm" onClick={() => onAssign?.(connection.id)}>Assign</Button>
          <Button intent="secondary" size="sm" onClick={() => onEdit?.(connection)}>Edit</Button>
          <Button intent="negative" size="sm" onClick={() => onDelete?.(connection.id)}>Delete</Button>
        </div>
      </div>
    </Card>
  )
}
