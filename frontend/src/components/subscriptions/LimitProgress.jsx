import Card from '../ui/Card.jsx'

export default function LimitProgress({ label, used, limit }) {
  const percentage = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const isOver = limit > 0 && used >= limit

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-[var(--color-ink)]">{label}</span>
        <span className={`text-xs font-medium ${isOver ? 'text-[var(--color-negative)]' : 'text-[var(--color-muted)]'}`}>
          {used} / {limit || '∞'}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--color-canvas)]">
        <div
          className={`h-2 rounded-full transition-colors ${isOver ? 'bg-[var(--color-negative)]' : 'bg-[var(--color-primary)]'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {isOver && <p className="mt-1 text-xs text-[var(--color-negative)]">Limit exceeded</p>}
    </Card>
  )
}
