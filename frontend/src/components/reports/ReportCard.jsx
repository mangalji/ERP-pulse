import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import Button from '../ui/Button.jsx'

export default function ReportCard({ report }) {
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Badge tone="primary">{report.type}</Badge>
          <h3 className="mt-2.5 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            {report.title}
          </h3>
          <p className="mt-1 text-xs text-[var(--color-muted)]">{report.date}</p>
        </div>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="h-9 w-9 shrink-0 text-[var(--color-border)]"
        >
          <path d="M6 3h9l4 4v14H6z" />
          <path d="M9 12h6M9 16h6M9 8h3" />
        </svg>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" intent="secondary">
          View Charts
        </Button>
        <Button size="sm" intent="secondary">
          Export PDF
        </Button>
        <Button size="sm" intent="secondary">
          Export Excel
        </Button>
      </div>
    </Card>
  )
}
