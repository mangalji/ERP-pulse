import Card from '../ui/Card.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import TrendBadge from './TrendBadge.jsx'
import { formatCurrency, formatNumber, formatPercent } from './format.js'

/**
 * MetricCard — a labeled metric with a big value and an optional trend delta.
 * `format` controls how `value` is rendered: 'currency' | 'number' | 'percent' | 'text'.
 */
export default function MetricCard({
  label,
  value,
  delta,
  format = 'number',
  currency = 'USD',
  hint,
  loading = false,
  inverse = false,
  className = '',
}) {
  const renderValue = () => {
    if (value === null || value === undefined) return '—'
    if (format === 'currency') return formatCurrency(value, currency)
    if (format === 'percent') return formatPercent(value)
    if (format === 'number') return formatNumber(value)
    return value
  }

  return (
    <Card className={`p-5 ${className}`}>
      <p className="text-xs font-medium text-[var(--color-muted)]">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className="mt-1 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
          {renderValue()}
        </p>
      )}
      <div className="mt-2 flex items-center gap-2">
        {!loading && <TrendBadge delta={delta} inverse={inverse} />}
        {!loading && hint && <span className="text-xs text-[var(--color-muted)]">{hint}</span>}
      </div>
    </Card>
  )
}
