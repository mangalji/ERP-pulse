const TONE_STYLES = {
  neutral: 'bg-[var(--color-canvas)] text-[var(--color-ink-soft)]',
  primary: 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]',
  netsuite: 'bg-[var(--color-netsuite-soft)] text-[var(--color-netsuite)]',
  positive: 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]',
  negative: 'bg-[var(--color-negative-soft)] text-[var(--color-negative)]',
}

export default function Badge({ children, tone = 'neutral', className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE_STYLES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
