import StatusBadge from './StatusBadge.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import { REPORT_TYPE_LABEL, formatBytes, formatDate, formatDuration } from './constants.js'

/**
 * Report history table. Shows report name, type, format, created by,
 * generated at, execution time, record count, file size, download
 * count, status, and actions (download / metadata).
 */
export default function HistoryTable({ rows = [], loading = false, onDownload, onView }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (!rows.length) {
    return (
      <EmptyState
        title="No report history"
        description="Reports you generate will appear here."
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {['Report', 'Type', 'Format', 'Created By', 'Generated At', 'Execution', 'Records', 'Size', 'Downloads', 'Status', 'Actions'].map((h) => (
              <th key={h} className="px-3 py-2.5 whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-canvas)]">
              <td className="px-3 py-2.5 font-medium text-[var(--color-ink)]">
                {REPORT_TYPE_LABEL[row.report_type] || row.report_type}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {REPORT_TYPE_LABEL[row.report_type] || row.report_type}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">{row.format}</td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {row.created_by_name || '—'}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {formatDate(row.generated_at)}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {formatDuration(row.execution_time_ms)}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {row.record_count?.toLocaleString() ?? '—'}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                {formatBytes(row.file_size)}
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">{row.download_count ?? 0}</td>
              <td className="px-3 py-2.5 whitespace-nowrap">
                <StatusBadge status={row.status} />
              </td>
              <td className="px-3 py-2.5 whitespace-nowrap">
                <div className="flex items-center gap-1">
                  {onDownload && row.status === 'COMPLETED' && (
                    <button
                      onClick={() => onDownload(row)}
                      aria-label="Download"
                      className="rounded-lg p-1.5 text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                      title="Download"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                        <path d="M12 3v12M7 11l5 5 5-5M4 21h16" />
                      </svg>
                    </button>
                  )}
                  {onView && (
                    <button
                      onClick={() => onView(row)}
                      aria-label="View metadata"
                      className="rounded-lg p-1.5 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                      title="View metadata"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
