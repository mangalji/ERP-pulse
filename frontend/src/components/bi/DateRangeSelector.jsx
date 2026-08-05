import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'

/**
 * DateRangeSelector — collapsible custom start/end date pickers.
 * Calls `onApply(start, end)` with YYYY-MM-DD strings.
 */
export default function DateRangeSelector({ onApply, onCancel, className = '' }) {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const handleApply = () => {
    if (start && end) onApply(start, end)
  }

  return (
    <div className={`rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4 ${className}`}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Input
          label="Start date"
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <Input
          label="End date"
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>
      <div className="mt-3 flex justify-end gap-2">
        {onCancel && (
          <Button intent="secondary" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button size="sm" onClick={handleApply} disabled={!start || !end}>
          Apply
        </Button>
      </div>
    </div>
  )
}
