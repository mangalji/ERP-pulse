export default function Input({ label, error, id, className = '', ...rest }) {
  return (
    <label className="flex flex-col gap-1.5" htmlFor={id}>
      {label && <span className="text-sm font-medium text-[var(--color-ink-soft)]">{label}</span>}
      <input
        id={id}
        className={`rounded-lg border px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none
          transition-colors placeholder:text-[var(--color-muted)]
          focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]
          ${error ? 'border-[var(--color-negative)]' : 'border-[var(--color-border)]'} ${className}`}
        {...rest}
      />
      {error && <span className="text-xs text-[var(--color-negative)]">{error}</span>}
    </label>
  )
}
