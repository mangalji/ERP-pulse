export default function Select({ label, children, className = '', id, ...rest }) {
  return (
    <label className={`flex flex-col gap-1.5 ${className}`} htmlFor={id}>
      {label && <span className="text-sm font-medium text-[var(--color-ink-soft)]">{label}</span>}
      <select
        id={id}
        className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
        {...rest}
      >
        {children}
      </select>
    </label>
  )
}
