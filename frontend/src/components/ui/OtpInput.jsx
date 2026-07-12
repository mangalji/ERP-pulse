import { useRef } from 'react'

/** Six-box OTP entry. Auto-advances focus; backspace steps back. */
export default function OtpInput({ length = 6, value, onChange }) {
  const inputsRef = useRef([])
  const digits = value.padEnd(length, ' ').split('').slice(0, length)

  const setDigit = (index, char) => {
    const next = digits.slice()
    next[index] = char || ' '
    onChange(next.join('').trimEnd())
  }

  const handleChange = (index, event) => {
    const char = event.target.value.replace(/\D/g, '').slice(-1)
    setDigit(index, char)
    if (char && index < length - 1) {
      inputsRef.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index, event) => {
    if (event.key === 'Backspace' && !digits[index].trim() && index > 0) {
      inputsRef.current[index - 1]?.focus()
    }
  }

  return (
    <div className="flex justify-between gap-2">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => (inputsRef.current[index] = el)}
          value={digit.trim()}
          onChange={(event) => handleChange(index, event)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          inputMode="numeric"
          maxLength={1}
          aria-label={`Digit ${index + 1} of ${length}`}
          className="font-mono-tabular h-12 w-full rounded-lg border border-[var(--color-border)]
            text-center text-lg font-medium text-[var(--color-ink)] outline-none
            focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
        />
      ))}
    </div>
  )
}
