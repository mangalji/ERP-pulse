import Card from '../ui/Card.jsx'

export default function ConnectionTable({ connections, onRowClick }) {
  if (!connections || connections.length === 0) {
    return (
      <Card className="p-5">
        <p className="text-sm text-[var(--color-muted)]">No connections found.</p>
      </Card>
    )
  }

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-3">
        {connections.map((conn) => (
          <div
            key={conn.id}
            onClick={() => onRowClick?.(conn)}
            className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-4 cursor-pointer hover:bg-[var(--color-canvas)]"
          >
            <div>
              <p className="text-sm font-medium text-[var(--color-ink)]">{conn.client_name || 'Unnamed Connection'}</p>
              <p className="text-xs text-[var(--color-muted)]">{conn.netsuite_account_id} · {conn.environment}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                conn.status === 'connected' ? 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]' :
                conn.status === 'error' ? 'bg-[var(--color-negative-soft)] text-[var(--color-negative)]' :
                'bg-[var(--color-canvas)] text-[var(--color-muted)]'
              }`}>{conn.status}</span>
              {conn.is_active && <span className="rounded-full bg-[var(--color-primary-soft)] px-2 py-1 text-xs font-medium text-[var(--color-primary)]">Active</span>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
