/**
 * Base button. `intent` chooses the visual language: "primary" is ERP
 * Pulse's own indigo action color; "netsuite" is reserved for anything
 * that initiates or touches a NetSuite action (see index.css token notes).
 */
const INTENT_STYLES = {
  primary:
    'bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-dark)] focus-visible:outline-[var(--color-primary)]',
  netsuite:
    'bg-[var(--color-netsuite)] text-white hover:brightness-95 focus-visible:outline-[var(--color-netsuite)]',
  secondary:
    'bg-white text-[var(--color-ink)] border border-[var(--color-border)] hover:bg-[var(--color-canvas)] focus-visible:outline-[var(--color-primary)]',
  ghost:
    'bg-transparent text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] focus-visible:outline-[var(--color-primary)]',
}

const SIZE_STYLES = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-6 py-3.5 text-base',
}

export default function Button({
  children,
  intent = 'primary',
  size = 'md',
  className = '',
  isLoading = false,
  disabled = false,
  type = 'button',
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
        disabled:cursor-not-allowed disabled:opacity-60
        ${INTENT_STYLES[intent]} ${SIZE_STYLES[size]} ${className}`}
      {...rest}
    >
      {isLoading && (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  )
}
