import { useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import HistoryTable from '../../components/reports-engine/HistoryTable.jsx'
import { reportsEngineApi } from '../../services/reportsEngine.js'

/**
 * Report history page. Lists all generated reports with metadata and
 * download / view actions.
 */
export default function ReportHistoryPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [offset, setOffset] = useState(0)
  const [count, setCount] = useState(0)
  const [metadata, setMetadata] = useState(null)
  const limit = 20

  const load = async (nextOffset = 0) => {
    setLoading(true)
    setError(null)
    try {
      const res = await reportsEngineApi.history.list({ limit, offset: nextOffset })
      const results = res?.results ?? res ?? []
      setRows(Array.isArray(results) ? results : [])
      setCount(res?.count ?? results.length)
      setOffset(nextOffset)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleDownload = async (row) => {
    try {
      const blob = await reportsEngineApi.history.download(row.id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${row.report_type}_${row.id}.${row.format.toLowerCase()}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      load(offset)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Download failed')
    }
  }

  const handleView = async (row) => {
    try {
      const data = await reportsEngineApi.history.metadata(row.id)
      setMetadata(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load metadata')
    }
  }

  const totalPages = Math.ceil(count / limit)
  const currentPage = Math.floor(offset / limit) + 1

  return (
    <ClientLayout title="Reports" breadcrumb="Report History">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Report History
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              {count} report{count === 1 ? '' : 's'} generated
            </p>
          </div>
          <Button intent="secondary" onClick={() => load(0)} disabled={loading}>
            Refresh
          </Button>
        </div>

        {error && (
          <div className="rounded-lg border border-[var(--color-negative)] bg-[var(--color-negative-soft)] px-4 py-3 text-sm text-[var(--color-negative)]">
            {error}
          </div>
        )}

        <Card className="p-5">
          <HistoryTable rows={rows} loading={loading} onDownload={handleDownload} onView={handleView} />
        </Card>

        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-[var(--color-muted)]">
              Page {currentPage} of {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => load(offset - limit)}>
                Previous
              </Button>
              <Button intent="secondary" size="sm" disabled={offset + limit >= count} onClick={() => load(offset + limit)}>
                Next
              </Button>
            </div>
          </div>
        )}

        {metadata && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button aria-label="Close" onClick={() => setMetadata(null)} className="absolute inset-0 bg-black/40" />
            <div className="relative w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <h3 className="mb-4 font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Report Metadata
              </h3>
              <dl className="flex flex-col gap-2 text-sm">
                {[
                  ['Report Type', metadata.report_type],
                  ['Format', metadata.format],
                  ['Status', metadata.status],
                  ['Records', metadata.record_count?.toLocaleString()],
                  ['File Size', metadata.file_size],
                  ['Execution Time', `${metadata.execution_time_ms} ms`],
                  ['Downloads', metadata.download_count],
                  ['Generated At', metadata.generated_at],
                  ['Created By', metadata.created_by],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2 last:border-0">
                    <dt className="text-[var(--color-muted)]">{k}</dt>
                    <dd className="font-medium text-[var(--color-ink)]">{v ?? '—'}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-5 flex justify-end">
                <Button intent="secondary" onClick={() => setMetadata(null)}>Close</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ClientLayout>
  )
}
