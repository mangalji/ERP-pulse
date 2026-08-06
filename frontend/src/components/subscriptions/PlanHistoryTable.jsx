import Card from '../ui/Card.jsx'

export default function PlanHistoryTable({ history }) {
  if (!history || history.length === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Plan History</h3>
        <p className="text-sm text-[var(--color-muted)]">No plan history available.</p>
      </Card>
    )
  }

  return (
    <Card className="p-5">
      <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Plan History</h3>
      <div className="flex flex-col gap-2">
        {history.map((item) => (
          <div key={item.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3">
            <div>
              <p className="text-sm font-medium text-[var(--color-ink)]">{item.plan__name}</p>
              <p className="text-xs text-[var(--color-muted)]">{item.status}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-[var(--color-muted)]">{item.start_date}</p>
              {item.end_date && <p className="text-xs text-[var(--color-muted)]">Ended: {item.end_date}</p>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
