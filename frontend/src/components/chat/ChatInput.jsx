import { forwardRef, useImperativeHandle, useRef, useState } from 'react'
import Button from '../ui/Button.jsx'

const ChatInput = forwardRef(function ChatInput({ onSend, disabled }, ref) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }))

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2 border-t border-[var(--color-border)] p-4">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) handleSubmit(event)
        }}
        rows={1}
        placeholder="Ask about revenue, customers, products..."
        className="max-h-32 flex-1 resize-none rounded-lg border border-[var(--color-border)] px-3.5 py-2.5
          text-sm outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
      />
      <Button type="submit" disabled={!value.trim()} isLoading={disabled}>
        Send
      </Button>
    </form>
  )
})

export default ChatInput
