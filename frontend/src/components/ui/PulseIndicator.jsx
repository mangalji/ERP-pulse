/**
 * The product's signature element — a breathing dot that represents live
 * connection state. Used small in the top nav (always visible) and large
 * on the Connect NetSuite page (as the hero visual). Color communicates
 * state: teal when connected/live, amber when action is needed.
 */
const STATE_STYLES = {
  connected: 'text-[var(--color-positive)]',
  disconnected: 'text-[var(--color-netsuite)]',
  thinking: 'text-[var(--color-primary)]',
}

export default function PulseIndicator({ state = 'disconnected', size = 'sm', label }) {
  const dimension = size === 'lg' ? 'h-4 w-4' : 'h-2 w-2'

  return (
    <span className="inline-flex items-center gap-2">
      <span className={`relative inline-flex ${dimension} ${STATE_STYLES[state]}`}>
        <span className="pulse-ring absolute inset-0" />
        <span className="relative inline-flex h-full w-full rounded-full bg-current" />
      </span>
      {label && <span className="text-sm text-[var(--color-ink-soft)]">{label}</span>}
    </span>
  )
}
