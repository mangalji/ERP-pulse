import Card from '../ui/Card.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import { formatCurrency, formatNumber, formatPercent } from './format.js'

/**
 * KpiCard — a stat tile with label, value, optional delta and icon.
 * `format` controls how `value` is rendered: 'currency' | 'number' | 'percent' | 'text'.
 */
export default function KpiCard({
  label,
  value,
  delta,
  format = 'number',
  icon,
  loading = false,
  footer,
  className = '',
}) {
  const renderValue = () => {
    if (value === null || value === undefined) return '—'
    if (format === 'currency') return formatCurrency(value)
    if (format === 'percent') return formatPercent(value)
    if (format === 'number') return formatNumber(value)
    return value
  }

  return (
    <Card className={`p-5 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-[var(--color-muted)]">{label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-8 w-20" />
          ) : (
            <p className="mt-1 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              {renderValue()}
            </p>
          )}
          {!loading && delta !== undefined && <TrendDelta delta={delta} />}
        </div>
        {icon && !loading && (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]">
            {icon}
          </span>
        )}
      </div>
      {footer && !loading && <div className="mt-3">{footer}</div>}
    </Card>
  )
}

function TrendDelta({ delta }) {
  if (delta === null || delta === undefined) return null
  const isUp = delta >= 0
  return (
    <span className={`mt-1 inline-flex items-center gap-1 text-xs font-medium ${isUp ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
      {isUp ? '↑' : '↓'} {Math.abs(Number(delta || 0)).toFixed(1)}%
    </span>
  )
}
