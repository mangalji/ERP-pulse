import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import { EXPORT_FORMATS } from './constants.js'

/**
 * Export dialog. Supports format, filename, email option, recipients,
 * subject, and message. Calls `onExport` with the chosen options.
 */
export default function ExportDialog({ open, reportTypeLabel, onClose, onExport, loading = false }) {
  const [format, setFormat] = useState('CSV')
  const [filename, setFilename] = useState(`${(reportTypeLabel || 'report').toLowerCase().replace(/\s+/g, '_')}`)
  const [emailEnabled, setEmailEnabled] = useState(false)
  const [recipients, setRecipients] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')

  const selectClass =
    'rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  if (!open) return null

  const handleExport = () => {
    onExport({
      format,
      filename,
      email: emailEnabled,
      recipients: emailEnabled
        ? recipients.split(',').map((r) => r.trim()).filter(Boolean)
        : [],
      subject,
      message,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button aria-label="Close" onClick={onClose} className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Export Report</h3>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-[var(--color-muted)] hover:bg-[var(--color-canvas)]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col gap-4">
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

          <Input
            label="Filename"
            id="export-filename"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
          />

          <label className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2.5">
            <input
              type="checkbox"
              checked={emailEnabled}
              onChange={(e) => setEmailEnabled(e.target.checked)}
              className="h-4 w-4 accent-[var(--color-primary)]"
            />
            <span className="text-sm font-medium text-[var(--color-ink-soft)]">Email the report</span>
          </label>

          {emailEnabled && (
            <>
              <Input
                label="Recipients (comma separated)"
                id="export-recipients"
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
                placeholder="a@example.com, b@example.com"
              />
              <Input
                label="Subject"
                id="export-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="AGSuite ERP Report"
              />
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Message</span>
                <textarea
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  rows={3}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Optional message"
                />
              </label>
            </>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button intent="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleExport} isLoading={loading}>
            Export
          </Button>
        </div>
      </div>
    </div>
  )
}
