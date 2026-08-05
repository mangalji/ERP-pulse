import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import { PRESETS, REPORT_TYPES } from './constants.js'

/**
 * Report filter bar. Supports:
 *  - Preset (today/yesterday/last_7_days/...)
 *  - Custom range (start_date / end_date)
 *  - Report type
 *  - Saved template
 *  - Clear + Apply
 *
 * `templates` is the list of saved templates (from templates API).
 */
export default function ReportFilter({ value, onChange, templates = [], onApply, loading = false }) {
  const [preset, setPreset] = useState(value?.preset || 'last_30_days')
  const [startDate, setStartDate] = useState(value?.start_date || '')
  const [endDate, setEndDate] = useState(value?.end_date || '')
  const [reportType, setReportType] = useState(value?.report_type || '')
  const [templateId, setTemplateId] = useState(value?.template_id || '')

  const apply = () => {
    onChange({
      preset: preset || '',
      start_date: startDate || '',
      end_date: endDate || '',
      report_type: reportType || '',
      template_id: templateId || '',
    })
    onApply?.()
  }

  const clear = () => {
    setPreset('')
    setStartDate('')
    setEndDate('')
    setReportType('')
    setTemplateId('')
    onChange({})
  }

  const selectClass =
    'rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[var(--color-ink-soft)]">Preset</span>
          <select className={selectClass} value={preset} onChange={(e) => setPreset(e.target.value)}>
            <option value="">All time</option>
            {PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[var(--color-ink-soft)]">Start Date</span>
          <input
            type="date"
            className={selectClass}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[var(--color-ink-soft)]">End Date</span>
          <input
            type="date"
            className={selectClass}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[var(--color-ink-soft)]">Report Type</span>
          <select className={selectClass} value={reportType} onChange={(e) => setReportType(e.target.value)}>
            <option value="">All types</option>
            {REPORT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="flex flex-1 flex-col gap-1.5 sm:max-w-xs">
          <span className="text-sm font-medium text-[var(--color-ink-soft)]">Saved Template</span>
          <select className={selectClass} value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            <option value="">No template</option>
            {(templates || []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2">
          <Button intent="secondary" onClick={clear} disabled={loading}>
            Clear
          </Button>
          <Button onClick={apply} isLoading={loading}>
            Apply
          </Button>
        </div>
      </div>
    </div>
  )
}
