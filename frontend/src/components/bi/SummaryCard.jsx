import Card from '../ui/Card.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import { formatCurrency, formatNumber, formatPercent } from './format.js'

/**
 * SummaryCard — a compact stat used in grouped summary grids.
 * `format` controls how `value` is rendered: 'currency' | 'number' | 'percent' | 'text'.
 */
export default function SummaryCard({
  label,
  value,
  format = 'number',
  icon,
  loading = false,
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
    <Card className={`p-4 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-[var(--color-muted)]">{label}</p>
        {icon && !loading && <span className="text-[var(--color-primary-dark)]">{icon}</span>}
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-16" />
      ) : (
        <p className="mt-1 font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
          {renderValue()}
        </p>
      )}
    </Card>
  )
}
