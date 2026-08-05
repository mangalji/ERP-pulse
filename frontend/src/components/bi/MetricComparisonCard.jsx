import Card from '../ui/Card.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import { formatCurrency, formatNumber, formatPercent } from './format.js'

/**
 * MetricComparisonCard — shows a metric with current vs previous period
 * values side by side, with a computed delta.
 */
export default function MetricComparisonCard({
  label,
  current,
  previous,
  format = 'number',
  currency = 'USD',
  loading = false,
  className = '',
}) {
  const renderValue = (value) => {
    if (value === null || value === undefined) return '—'
    if (format === 'currency') return formatCurrency(value, currency)
    if (format === 'percent') return formatPercent(value)
    if (format === 'number') return formatNumber(value)
    return value
  }

  const delta =
    current === null || current === undefined || previous === null || previous === undefined || previous === 0
      ? null
      : ((current - previous) / previous) * 100

  const isUp = delta !== null && delta >= 0

  return (
    <Card className={`p-5 ${className}`}>
      <p className="text-xs font-medium text-[var(--color-muted)]">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-24" />
      ) : (
        <p className="mt-1 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
          {renderValue(current)}
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-[var(--color-border)] pt-3">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-muted)]">Current</p>
          <p className="mt-0.5 text-sm font-medium text-[var(--color-ink)]">{renderValue(current)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--color-muted)]">Previous</p>
          <p className="mt-0.5 text-sm font-medium text-[var(--color-ink-soft)]">{renderValue(previous)}</p>
        </div>
      </div>
      {delta !== null && (
        <span className={`mt-2 inline-block text-xs font-semibold ${isUp ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
          {isUp ? '↑' : '↓'} {Math.abs(Number(delta)).toFixed(1)}% vs previous
        </span>
      )}
    </Card>
  )
}
