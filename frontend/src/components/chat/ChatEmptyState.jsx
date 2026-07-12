import SuggestedPrompts from './SuggestedPrompts.jsx'

export default function ChatEmptyState({ prompts, onSelectPrompt }) {
  return (
    <div className="mx-auto flex max-w-lg flex-1 flex-col items-center justify-center gap-6 text-center">
      <span className="relative inline-flex h-8 w-8 text-[var(--color-primary)]">
        <span className="pulse-ring absolute inset-0" />
        <span className="relative inline-flex h-full w-full rounded-full bg-current" />
      </span>
      <div>
        <h2 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
          Ask ERP Pulse anything
        </h2>
        <p className="mt-1.5 text-sm text-[var(--color-muted)]">
          Answers are grounded in your NetSuite data — never invented.
        </p>
      </div>
      <SuggestedPrompts prompts={prompts} onSelect={onSelectPrompt} />
    </div>
  )
}
