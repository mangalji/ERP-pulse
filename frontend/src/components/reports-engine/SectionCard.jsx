import Card from '../ui/Card.jsx'

/** Titled section wrapper — a Card with a header row and body. */
export default function SectionCard({ title, subtitle, actions, children, className = '' }) {
  return (
    <Card className={`p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            {title && (
              <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                {title}
              </h3>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-[var(--color-muted)]">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </Card>
  )
}
