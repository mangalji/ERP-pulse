import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import { EXPORT_FORMATS, REPORT_TYPES, SCHEDULE_FREQUENCIES } from './constants.js'

/**
 * Schedule dialog. Exposes only Daily / Weekly / Monthly / Quarterly /
 * Yearly (Advanced Cron is hidden for now). Creates or edits a schedule.
 */
export default function ScheduleDialog({ open, schedule, onClose, onSave, loading = false }) {
  const [name, setName] = useState(schedule?.name || '')
  const [reportType, setReportType] = useState(schedule?.report_type || '')
  const [frequency, setFrequency] = useState(schedule?.frequency || 'DAILY')
  const [format, setFormat] = useState(schedule?.format || 'CSV')
  const [recipients, setRecipients] = useState(schedule?.config?.recipients?.join(', ') || '')
  const [subject, setSubject] = useState(schedule?.config?.subject || '')

  const selectClass =
    'rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  if (!open) return null

  const handleSave = () => {
    onSave({
      name,
      report_type: reportType,
      frequency,
      format,
      config: {
        recipients: recipients.split(',').map((r) => r.trim()).filter(Boolean),
        subject,
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button aria-label="Close" onClick={onClose} className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
            {schedule ? 'Edit Schedule' : 'New Schedule'}
          </h3>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-[var(--color-muted)] hover:bg-[var(--color-canvas)]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col gap-4">
          <Input label="Schedule Name" id="schedule-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Monthly sales report" />

          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[var(--color-ink-soft)]">Report Type</span>
            <select className={selectClass} value={reportType} onChange={(e) => setReportType(e.target.value)}>
              <option value="">Select type</option>
              {REPORT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[var(--color-ink-soft)]">Frequency</span>
              <select className={selectClass} value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                {SCHEDULE_FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[var(--color-ink-soft)]">Format</span>
              <select className={selectClass} value={format} onChange={(e) => setFormat(e.target.value)}>
                {EXPORT_FORMATS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <Input
            label="Recipients (comma separated)"
            id="schedule-recipients"
            value={recipients}
            onChange={(e) => setRecipients(e.target.value)}
            placeholder="a@example.com, b@example.com"
          />
          <Input
            label="Subject"
            id="schedule-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Scheduled report"
          />
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button intent="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} isLoading={loading}>
            {schedule ? 'Save' : 'Create'}
          </Button>
        </div>
      </div>
    </div>
  )
}
