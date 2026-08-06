import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'

export default function UsageCard({ modules }) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Usage</h3>
      <div className="flex flex-col gap-4">
        {modules.map((mod) => (
          <div key={mod.module_code} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3">
            <div>
              <p className="text-sm font-medium text-[var(--color-ink)]">{mod.module_name}</p>
              <p className="text-xs text-[var(--color-muted)]">{mod.module_code}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                {mod.usage_count || 0} / {mod.usage_limit || '∞'}
              </p>
              <p className="text-xs text-[var(--color-muted)]">
                {mod.remaining !== null && mod.remaining !== undefined ? `${mod.remaining} remaining` : 'Unlimited'}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
