/**
 * Page header used at the top of each superadmin page.
 * Shows a title, optional subtitle, and an action slot.
 */
export default function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-[var(--color-muted)]">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
