import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'

/**
 * Report type card. Shows the report label with an optional description
 * and a primary action (e.g. "Generate").
 */
export default function ReportCard({ label, description, icon, onGenerate, isFavorite }) {
  return (
    <Card className="flex flex-col p-4">
      <div className="flex flex-1 flex-col">
        <div className="flex items-start justify-between">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            {icon || <DefaultIcon />}
          </span>
          {isFavorite && (
            <svg viewBox="0 0 24 24" fill="var(--color-netsuite)" stroke="var(--color-netsuite)" strokeWidth="1.5" className="h-4 w-4">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          )}
        </div>
        <h3 className="mt-3 font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">{label}</h3>
        {description && <p className="mt-1 line-clamp-2 text-xs text-[var(--color-muted)]">{description}</p>}
      </div>
      <Button intent="secondary" size="sm" className="mt-3 w-full" onClick={onGenerate}>
        Generate
      </Button>
    </Card>
  )
}

function DefaultIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M14 3v4h4M9 13h6M9 17h6M9 9h2" />
    </svg>
  )
}
