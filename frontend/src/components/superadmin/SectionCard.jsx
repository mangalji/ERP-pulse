import Card from '../ui/Card.jsx'

/**
 * Section container with an optional title and action slot.
 * Used to group related content on a page.
 */
export default function SectionCard({ title, subtitle, actions, children, className = '' }) {
  return (
    <Card className={`p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            {title && (
              <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-sm text-[var(--color-muted)]">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </Card>
  )
}
