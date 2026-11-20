import { memo } from 'react'
import Input from '../ui/Input.jsx'
import { preventOcrNumberStep, blurOcrNumberOnWheel } from '../../utils/ocrNumericInput.js'
import { toInputValue } from '../../utils/ocrShared.js'

const OcrFieldInput = memo(function OcrFieldInput({ field, value, editable, onChange, idPrefix = 'ocr' }) {
  const displayValue = toInputValue(value)
  if (!editable) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-ink-soft)]">{field.label}</span>
        <div className="min-h-[46px] rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3.5 py-2.5 text-sm text-[var(--color-ink)]">
          {displayValue || '--'}
        </div>
      </div>
    )
  }
  return (
    <Input
      id={`${idPrefix}-${field.key}`}
      label={field.label}
      type={field.type}
      value={displayValue}
      step={field.type === 'number' ? 'any' : undefined}
      className={field.type === 'number' ? 'ocr-number-input' : ''}
      onKeyDown={field.type === 'number' ? preventOcrNumberStep : undefined}
      onWheel={field.type === 'number' ? blurOcrNumberOnWheel : undefined}
      onChange={(event) => onChange(field.key, event.target.value)}
    />
  )
})

export default OcrFieldInput
