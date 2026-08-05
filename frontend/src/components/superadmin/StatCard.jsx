import Card from '../ui/Card.jsx'

/**
 * Statistic card used on the superadmin dashboard.
 * Displays a label, a value, and an optional icon.
 */
export default function StatCard({ label, value, icon, className = '' }) {
  return (
    <Card className={`p-5 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[var(--color-muted)]">{label}</p>
          <p className="mt-2 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            {value ?? '--'}
          </p>
        </div>
        {icon && (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            {icon}
          </span>
        )}
      </div>
    </Card>
  )
}
