export default function ChatMessage({ role, text }) {
  const isAssistant = role === 'assistant'

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isAssistant
            ? 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-ink)]'
            : 'bg-[var(--color-primary)] text-white'
        }`}
      >
        {text}
      </div>
    </div>
  )
}
