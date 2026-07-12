export default function SuggestedPrompts({ prompts, onSelect }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          onClick={() => onSelect(prompt)}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3
            text-left text-sm text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-primary)]
            hover:text-[var(--color-ink)]"
        >
          {prompt}
        </button>
      ))}
    </div>
  )
}
