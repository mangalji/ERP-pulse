/**
 * FilterBar — a horizontal bar of preset time-range buttons (Today,
 * Yesterday, Last 7/30 Days, This Month, etc.) plus a "Custom" trigger.
 */
const PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 Days' },
  { value: 'last_30_days', label: 'Last 30 Days' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'this_quarter', label: 'This Quarter' },
  { value: 'this_year', label: 'This Year' },
]

export default function FilterBar({ value, onChange, onCustom, className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1 ${className}`}>
      {PRESETS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            value === p.value
              ? 'bg-[var(--color-primary)] text-white'
              : 'text-[var(--color-muted)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'
          }`}
        >
          {p.label}
        </button>
      ))}
      <button
        onClick={onCustom}
        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
          value === 'custom'
            ? 'bg-[var(--color-primary)] text-white'
            : 'text-[var(--color-muted)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'
        }`}
      >
        Custom
      </button>
    </div>
  )
}
