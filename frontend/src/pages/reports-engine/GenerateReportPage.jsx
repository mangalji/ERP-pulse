import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import ReportFilter from '../../components/reports-engine/ReportFilter.jsx'
import ReportPreview from '../../components/reports-engine/ReportPreview.jsx'
import ExportDialog from '../../components/reports-engine/ExportDialog.jsx'
import { REPORT_TYPES } from '../../components/reports-engine/constants.js'
import { reportsEngineApi } from '../../services/reportsEngine.js'

/**
 * Report generation flow: Generate → Preview → Export → History.
 * User selects a report type + filters, previews the data, then exports
 * it (optionally by email). Existing history is shown at the bottom.
 */
export default function GenerateReportPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [reportType, setReportType] = useState(params.get('type') || 'SALES')
  const [filters, setFilters] = useState({ preset: 'last_30_days' })
  const [templates, setTemplates] = useState([])
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)
  const [exportOpen, setExportOpen] = useState(false)
  const [history, setHistory] = useState([])
  const [toast, setToast] = useState(null)

  const loadTemplatesAndHistory = async () => {
    const [templ] = await Promise.all([
      reportsEngineApi.templates.list({ limit: 50, offset: 0 }).catch(() => ({ results: [] })),
      reportsEngineApi.history.list({ limit: 5, offset: 0 }).catch(() => ({ results: [] })),
    ])
    setTemplates(templ?.results ?? templ ?? [])
  }

  useEffect(() => {
    loadTemplatesAndHistory()
  }, [])

  const showToast = (message) => {
    setToast(message)
    setTimeout(() => setToast(null), 3000)
  }

  const handlePreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await reportsEngineApi.reports.preview({
        report_type: reportType,
        preset: filters.preset || '',
        start_date: filters.start_date || '',
        end_date: filters.end_date || '',
      })
      setPreview(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to preview report')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const data = await reportsEngineApi.reports.generate({
        report_type: reportType,
        format: 'CSV',
        preset: filters.preset || '',
        start_date: filters.start_date || '',
        end_date: filters.end_date || '',
      })
      showToast('Report generation started in the background.')
      navigate('/app/reports-engine/history')
      return data
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to generate report')
    } finally {
      setGenerating(false)
    }
  }

  const handleExport = async (options) => {
    setError(null)
    try {
      // If emailing, use the email endpoint (requires a completed report).
      // Otherwise trigger an async generation in the chosen format.
      const data = await reportsEngineApi.reports.generate({
        report_type: reportType,
        format: options.format,
        preset: filters.preset || '',
        start_date: filters.start_date || '',
        end_date: filters.end_date || '',
      })
      setExportOpen(false)
      showToast(`Report queued as ${options.format}.`)

      if (options.email && options.recipients.length) {
        await reportsEngineApi.reports.email({
          history_id: data.id,
          recipients: options.recipients,
          subject: options.subject || 'AGSuite ERP Report',
          message: options.message || '',
        })
        showToast('Report generated and queued for email.')
      }
      navigate('/app/reports-engine/history')
    } catch (err) {
      setError(err.payload?.message || err.message || 'Export failed')
    }
  }

  const selectClass =
    'rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  return (
    <ClientLayout title="Reports" breadcrumb="Generate Report">
      <div className="flex flex-col gap-6">
        {toast && (
          <div className="rounded-lg border border-[var(--color-positive)] bg-[var(--color-positive-soft)] px-4 py-3 text-sm text-[var(--color-positive)]">
            {toast}
          </div>
        )}

        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Generate Report
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">Generate → Preview → Export → History</p>
          </div>
          <div className="flex items-center gap-2">
            <Button intent="secondary" onClick={handlePreview} isLoading={loading}>
              Preview
            </Button>
            <Button onClick={handleGenerate} isLoading={generating}>
              Generate
            </Button>
          </div>
        </div>

        <Card className="p-5">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[var(--color-ink-soft)]">Report Type</span>
            <select className={`${selectClass} sm:max-w-md`} value={reportType} onChange={(e) => setReportType(e.target.value)}>
              {REPORT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        </Card>

        <ReportFilter
          value={filters}
          onChange={setFilters}
          templates={templates}
          onApply={handlePreview}
          loading={loading}
        />

        {error && <ErrorState message={error} onRetry={() => (preview ? null : handlePreview())} />}

        {preview && (
          <ReportPreview payload={preview} filters={filters} onExport={() => setExportOpen(true)} />
        )}

        <ExportDialog
          open={exportOpen}
          reportTypeLabel={REPORT_TYPES.find((t) => t.value === reportType)?.label}
          onClose={() => setExportOpen(false)}
          onExport={handleExport}
          loading={generating}
        />
      </div>
    </ClientLayout>
  )
}
