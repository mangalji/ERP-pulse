/**
 * TrendBadge — small pill showing an up/down/flat delta vs a previous period.
 * delta is a percentage (e.g. 12.5). Benefits = true means up is green.
 */
export default function TrendBadge({ delta, inverse = false, className = '' }) {
  if (delta === null || delta === undefined) {
    return (
      <span className={`inline-flex items-center rounded-full bg-[var(--color-canvas)] px-2 py-0.5 text-xs font-medium text-[var(--color-muted)] ${className}`}>
        —
      </span>
    )
  }

  const isUp = delta >= 0
  const positive = inverse ? !isUp : isUp
  const tone = delta === 0 || positive
    ? (delta === 0 ? 'text-[var(--color-muted)] bg-[var(--color-canvas)]' : 'text-[var(--color-positive)] bg-[var(--color-positive-soft)]')
    : 'text-[var(--color-negative)] bg-[var(--color-negative-soft)]'

  const arrow = delta === 0 ? '→' : isUp ? '↑' : '↓'

  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${tone} ${className}`}>
      {arrow} {Math.abs(Number(delta || 0)).toFixed(1)}%
    </span>
  )
}
