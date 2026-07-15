import { useState } from 'react'

export default function ChatMessage({ role, text, timestamp, onRegenerate, showContextBadge }) {
  const isAssistant = role === 'assistant'
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isAssistant
            ? 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-ink)]'
            : 'bg-[var(--color-primary)] text-white'
        }`}
      >
        {showContextBadge && isAssistant && (
          <div className="mb-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-[var(--color-netsuite-soft)] px-2 py-0.5 text-xs font-medium text-[var(--color-netsuite)]">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3 w-3">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
              Using Business Context
            </span>
          </div>
        )}
        <p className="whitespace-pre-wrap">{text}</p>
        <div className="mt-2 flex items-center gap-2">
          {timestamp && (
            <span className="text-xs opacity-60">{new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          )}
          {isAssistant && (
            <div className="flex items-center gap-1">
              <button
                onClick={handleCopy}
                className="text-xs opacity-60 hover:opacity-100 transition-opacity"
                title="Copy response"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="text-xs opacity-60 hover:opacity-100 transition-opacity"
                  title="Regenerate response"
                >
                  Regenerate
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
