import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import { formatCurrency, formatNumber, formatPercent } from './format.js'

const SEVERITY_TONE = {
  critical: 'negative',
  warning: 'netsuite',
  info: 'neutral',
}

const SEVERITY_ICON = {
  critical: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6M12 17h.01" />
    </svg>
  ),
  warning: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  ),
  info: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  ),
}

/**
 * AlertCard — renders a single executive alert with severity.
 * `alert` is the backend object: { severity, title, message, metric, value, currency, unit }.
 */
export default function AlertCard({ alert, className = '' }) {
  const severity = alert?.severity || 'info'
  const tone = SEVERITY_TONE[severity] || 'neutral'

  const renderValue = () => {
    const v = alert?.value
    if (v === null || v === undefined) return null
    if (alert.metric === 'ocr_success_rate') return `${v}%`
    return v
  }

  return (
    <Card className={`flex items-start gap-3 p-4 ${className}`}>
      <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
        severity === 'critical'
          ? 'bg-[var(--color-negative-soft)] text-[var(--color-negative)]'
          : severity === 'warning'
            ? 'bg-[var(--color-netsuite-soft)] text-[var(--color-netsuite)]'
            : 'bg-[var(--color-canvas)] text-[var(--color-muted)]'
      }`}>
        {SEVERITY_ICON[severity] || SEVERITY_ICON.info}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-[var(--color-ink)]">{alert?.title}</p>
          <Badge tone={tone}>{String(severity).charAt(0).toUpperCase()}</Badge>
        </div>
        {alert?.message && <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{alert.message}</p>}
        {renderValue() !== null && (
          <p className="mt-1 text-xs font-mono-tabular text-[var(--color-muted)]">Value: {renderValue()}</p>
        )}
      </div>
    </Card>
  )
}
