import Card from '../ui/Card.jsx'

const FORMATTERS = {
  currency: (v) => `$${v.toLocaleString('en-US')}`,
  number: (v) => v.toLocaleString('en-US'),
  score: (v) => `${v}/100`,
}

export default function KpiCard({ label, value, delta, format = 'number' }) {
  const isPositive = delta >= 0
  const formatted = (FORMATTERS[format] ?? FORMATTERS.number)(value)

  return (
    <Card className="p-5">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="font-mono-tabular mt-2 text-2xl font-semibold text-[var(--color-ink)]">{formatted}</p>
      <p
        className={`mt-1.5 inline-flex items-center gap-1 text-xs font-medium ${
          isPositive ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'
        }`}
      >
        <span aria-hidden="true">{isPositive ? '\u2191' : '\u2193'}</span>
        {Math.abs(delta)}% vs last month
      </p>
    </Card>
  )
}
