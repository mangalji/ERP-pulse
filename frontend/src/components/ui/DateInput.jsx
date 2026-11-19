import { useEffect, useRef, useState } from 'react'

function formatDisplay(value) {
  if (!value) return ''
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value
}

function parseDisplay(value) {
  const match = String(value).trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (!match) return ''
  const day = match[1].padStart(2, '0')
  const month = match[2].padStart(2, '0')
  const year = match[3]
  const candidate = new Date(Number(year), Number(month) - 1, Number(day))
  if (candidate.getFullYear() !== Number(year) || candidate.getMonth() !== Number(month) - 1 || candidate.getDate() !== Number(day)) return ''
  return `${year}-${month}-${day}`
}

export default function DateInput({ value, onChange, className = '', ...props }) {
  const nativeRef = useRef(null)
  const [draft, setDraft] = useState(formatDisplay(value))

  useEffect(() => setDraft(formatDisplay(value)), [value])

  const emit = (next) => onChange?.({ target: { value: next } })
  const commit = () => {
    const parsed = parseDisplay(draft)
    if (draft === '' || parsed) emit(parsed)
    else setDraft(formatDisplay(value))
  }

  return (
    <div className="relative">
      <input
        {...props}
        type="text"
        inputMode="numeric"
        placeholder="dd/mm/yyyy"
        value={draft}
        onChange={(event) => setDraft(event.target.value.replace(/[^\d/]/g, '').slice(0, 10))}
        onBlur={commit}
        className={`w-full ${className}`}
      />
      <button type="button" aria-label="Choose date" onClick={() => nativeRef.current?.showPicker?.() || nativeRef.current?.click()} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-muted)]">
        ▣
      </button>
      <input
        ref={nativeRef}
        type="date"
        value={value || ''}
        onChange={(event) => { emit(event.target.value); setDraft(formatDisplay(event.target.value)) }}
        tabIndex={-1}
        aria-hidden="true"
        className="pointer-events-none absolute right-2 top-1/2 h-0 w-0 opacity-0"
      />
    </div>
  )
}
