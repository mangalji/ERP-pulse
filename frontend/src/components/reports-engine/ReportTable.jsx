import EmptyState from '../ui/EmptyState.jsx'
import Skeleton from '../ui/Skeleton.jsx'

/**
 * Generic report table rendering a normalized { headers, rows } payload.
 * `emptyTitle`/`emptyDescription` control the empty state.
 */
export default function ReportTable({ headers = [], rows = [], loading = false, emptyTitle, emptyDescription }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    )
  }

  if (!headers.length || !rows.length) {
    return (
      <EmptyState
        title={emptyTitle || 'No data to display'}
        description={emptyDescription || 'Generate a report to see results here.'}
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {headers.map((header) => (
              <th
                key={header}
                className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)] whitespace-nowrap"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-canvas)]">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-3 py-2.5 text-[var(--color-ink)] whitespace-nowrap">
                  {cell === null || cell === undefined || cell === '' ? '—' : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
