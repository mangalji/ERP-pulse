export default function EmptyState({ title, description, action, actionLabel }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-sidebar-soft)]">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6 text-[var(--color-muted)]">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 9h6M9 13h6M9 17h4" />
        </svg>
      </div>
      <div>
        <p className="text-sm font-semibold text-[var(--color-ink)]">{title}</p>
        {description && <p className="mt-1 text-sm text-[var(--color-muted)]">{description}</p>}
      </div>
      {action && actionLabel && (
        <button onClick={action} className="mt-2 text-sm font-medium text-[var(--color-primary)] hover:underline">
          {actionLabel}
        </button>
      )}
    </div>
  )
}
