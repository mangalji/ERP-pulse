export default function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-negative-soft)]">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6 text-[var(--color-negative)]">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
      </div>
      <div>
        <p className="text-sm font-semibold text-[var(--color-ink)]">Something went wrong</p>
        {message && <p className="mt-1 text-sm text-[var(--color-muted)]">{message}</p>}
      </div>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-sm font-medium text-[var(--color-primary)] hover:underline">
          Try again
        </button>
      )}
    </div>
  )
}
