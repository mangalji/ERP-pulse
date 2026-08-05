import EmptyState from '../ui/EmptyState.jsx'
import LoadingState from './LoadingState.jsx'

/**
 * Generic data table.
 * Handles loading, empty, and error states.
 * Renders a responsive table with columns defined by the caller.
 */
export default function DataTable({
  columns,
  rows,
  loading = false,
  error = null,
  emptyTitle = 'No data found',
  emptyDescription = 'There are no records to display yet.',
  onRetry,
  rowKey = 'id',
  emptyAction,
  emptyActionLabel,
}) {
  if (loading) {
    return <LoadingState rows={4} />
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-negative-soft)]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6 text-[var(--color-negative)]">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--color-ink)]">Something went wrong</p>
          <p className="mt-1 text-sm text-[var(--color-muted)]">{error}</p>
        </div>
        {onRetry && (
          <button onClick={onRetry} className="mt-2 text-sm font-medium text-[var(--color-primary)] hover:underline">
            Try again
          </button>
        )}
      </div>
    )
  }

  if (!rows || rows.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
        actionLabel={emptyActionLabel}
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {columns.map((col) => (
              <th
                key={col.key || col.header}
                className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[rowKey]} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-canvas)]">
              {columns.map((col) => (
                <td key={col.key || col.header} className="px-4 py-3 text-[var(--color-ink)]">
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
