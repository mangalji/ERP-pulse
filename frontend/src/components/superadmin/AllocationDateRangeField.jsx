import { useEffect, useRef, useState } from 'react'
import Button from '../ui/Button.jsx'
import DateInput from '../ui/DateInput.jsx'

const PRESET_OPTIONS = [
  { value: '7_days', label: '7 days' },
  { value: '15_days', label: '15 days' },
  { value: '30_days', label: '30 days' },
  { value: '6_months', label: '6 months' },
  { value: '1_year', label: '1 year' },
]

function formatDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function addMonths(date, months) {
  const result = new Date(date)
  result.setMonth(result.getMonth() + months)
  return result
}

function getPresetDates(value) {
  const today = new Date()
  const next = new Date(today)
  if (value.endsWith('_days')) next.setDate(next.getDate() + Number(value.split('_')[0]) - 1)
  if (value === '6_months') next.setTime(addMonths(today, 6).getTime())
  if (value === '1_year') next.setTime(addMonths(today, 12).getTime())
  return { start: formatDate(today), end: formatDate(next) }
}

export default function AllocationDateRangeField({ label, start, end, onChange, error, disabled = false }) {
  const [open, setOpen] = useState(false)
  const [draftStart, setDraftStart] = useState(start || '')
  const [draftEnd, setDraftEnd] = useState(end || '')
  const [preset, setPreset] = useState('custom')
  const [draftError, setDraftError] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    if (!open) {
      setDraftStart(start || '')
      setDraftEnd(end || '')
    }
  }, [open, start, end])

  useEffect(() => {
    const handleOutside = (event) => {
      if (open && ref.current && !ref.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  const apply = () => {
    const selectedRange = preset === 'custom' ? { start: draftStart, end: draftEnd } : getPresetDates(preset)
    if (!selectedRange.start || !selectedRange.end) {
      setDraftError('Select both start and end dates.')
      return
    }
    if (selectedRange.end < selectedRange.start) {
      setDraftError('End date must be on or after the start date.')
      return
    }
    onChange(selectedRange)
    setOpen(false)
  }

  const choosePreset = (value) => {
    setPreset(value)
    setDraftError('')
    if (value === 'custom') return
    const range = getPresetDates(value)
    setDraftStart(range.start)
    setDraftEnd(range.end)
  }

  return (
    <div ref={ref} className="relative">
      <p className="mb-1.5 text-sm font-medium text-[var(--color-ink-soft)]">{label}</p>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
        className={`flex w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-left text-sm text-[var(--color-ink)] ${disabled ? 'cursor-default opacity-80' : 'cursor-pointer'}`}
      >
        <span>{start && end ? `${start} - ${end}` : 'Select date range'}</span>
        <span className="text-[var(--color-muted)]">⌄</span>
      </button>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {open && (
        <div className="absolute z-30 mt-2 w-full min-w-[320px] rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xl">
          <p className="mb-2 text-sm font-medium text-[var(--color-muted)]">Date range</p>
          <select value={preset} onChange={(event) => choosePreset(event.target.value)} className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)]">
            <option value="custom">Custom</option>
            {PRESET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="text-xs font-medium text-[var(--color-muted)]">
              Start
              <DateInput value={draftStart} onChange={(event) => setDraftStart(event.target.value)} className="mt-1 rounded-lg border border-[var(--color-border)] bg-white px-2 py-2 pr-8 text-sm font-normal text-[var(--color-ink)]" />
            </label>
            <label className="text-xs font-medium text-[var(--color-muted)]">
              End
              <DateInput value={draftEnd} onChange={(event) => setDraftEnd(event.target.value)} className="mt-1 rounded-lg border border-[var(--color-border)] bg-white px-2 py-2 pr-8 text-sm font-normal text-[var(--color-ink)]" />
            </label>
          </div>
          {(draftError || error) && <p className="mt-2 text-xs text-red-600">{draftError || error}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button type="button" intent="secondary" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="button" size="sm" onClick={apply}>Apply</Button>
          </div>
        </div>
      )}
    </div>
  )
}
