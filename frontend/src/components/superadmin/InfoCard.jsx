import Card from '../ui/Card.jsx'

/**
 * Label/value pair used inside detail drawers and info panels.
 */
export default function InfoCard({ title, items = [] }) {
  return (
    <Card className="p-5">
      {title && (
        <h3 className="mb-4 font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
          {title}
        </h3>
      )}
      <dl className="flex flex-col gap-3">
        {items.map((item) => (
          <div key={item.label} className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
              {item.label}
            </dt>
            <dd className="text-sm text-[var(--color-ink)]">{item.value ?? '—'}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}
