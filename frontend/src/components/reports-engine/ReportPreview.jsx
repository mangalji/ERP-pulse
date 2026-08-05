import Card from '../ui/Card.jsx'
import ReportTable from './ReportTable.jsx'
import { REPORT_TYPE_LABEL, formatBytes, formatDuration } from './constants.js'

/**
 * Report preview. Displays summary, applied filters, estimated records,
 * estimated file size, estimated duration, and the preview table.
 */
export default function ReportPreview({ payload, filters, onExport }) {
  if (!payload) return null

  const summary = payload.summary || {}
  const headers = payload.headers || []
  const rows = payload.rows || []
  const rowCount = payload.row_count ?? rows.length
  const estSize = payload.estimated_file_size ?? 0
  const estDuration = payload.estimated_duration_ms ?? 0

  const summaryEntries = Object.entries(summary).filter(([, v]) => v !== null && v !== undefined && v !== '')

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Preview
            </h3>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              {REPORT_TYPE_LABEL[payload.report_type] || payload.report_type}
            </p>
          </div>
          {onExport && (
            <button
              onClick={onExport}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)]"
            >
              Export
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <PreviewStat label="Estimated Records" value={rowCount?.toLocaleString() ?? '—'} />
          <PreviewStat label="Estimated File Size" value={formatBytes(estSize)} />
          <PreviewStat label="Estimated Duration" value={formatDuration(estDuration)} />
          <PreviewStat label="Applied Preset" value={filters?.preset || 'Custom / All'} />
        </div>

        {summaryEntries.length > 0 && (
          <div className="mt-4 rounded-lg bg-[var(--color-canvas)] p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Summary</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {summaryEntries.map(([k, v]) => (
                <div key={k} className="text-sm">
                  <span className="text-[var(--color-muted)]">{k}: </span>
                  <span className="font-medium text-[var(--color-ink)]">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {filters?.start_date || filters?.end_date ? (
          <div className="mt-3 text-xs text-[var(--color-muted)]">
            Custom range: {filters.start_date || 'start'} → {filters.end_date || 'now'}
          </div>
        ) : null}
      </Card>

      <Card className="p-5">
        <h3 className="mb-3 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
          Preview Table
        </h3>
        <ReportTable headers={headers} rows={rows.slice(0, 50)} emptyTitle="No preview rows" />
      </Card>
    </div>
  )
}

function PreviewStat({ label, value }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] p-3">
      <p className="text-xs font-medium text-[var(--color-muted)]">{label}</p>
      <p className="mt-1 font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">{value}</p>
    </div>
  )
}
