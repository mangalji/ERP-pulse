import { useState } from 'react'

function EyeIcon({ hidden = false }) {
  return hidden ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.5C2.75 10.14 2 12 2 12s3.58 6 10 6c1.54 0 2.87-.35 4-.86M9.88 5.24A10.75 10.75 0 0 1 12 5c6.42 0 10 7 10 7s-.76 1.86-1.98 3.5M3 3l18 18" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.12 14.12A3 3 0 0 1 9.88 9.88" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2 12s3.58-6 10-6 10 6 10 6-3.58 6-10 6S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

export default function Input({ label, error, id, type = 'text', className = '', ...rest }) {
  const [showValue, setShowValue] = useState(false)
  const isPassword = type === 'password'
  const inputType = isPassword && showValue ? 'text' : type

  return (
    <label className="flex flex-col gap-1.5" htmlFor={id}>
      {label && <span className="text-sm font-medium text-[var(--color-ink-soft)]">{label}</span>}
      <div className="relative">
        <input
          id={id}
          type={inputType}
          className={`w-full rounded-lg border px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none
            transition-colors placeholder:text-[var(--color-muted)]
            focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]
            ${isPassword ? 'pr-11' : ''}
            ${error ? 'border-[var(--color-negative)]' : 'border-[var(--color-border)]'} ${className}`}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowValue((visible) => !visible)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-[var(--color-muted)] hover:text-[var(--color-ink)]"
            aria-label={showValue ? 'Hide credential' : 'Show credential'}
            title={showValue ? 'Hide credential' : 'Show credential'}
          >
            <EyeIcon hidden={showValue} />
          </button>
        )}
      </div>
      {error && <span className="text-xs text-[var(--color-negative)]">{error}</span>}
    </label>
  )
}
