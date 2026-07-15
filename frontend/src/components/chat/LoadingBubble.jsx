export default function LoadingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3.5">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-primary)] opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--color-primary)]" />
        </span>
        <span className="text-xs text-[var(--color-muted)]">Thinking</span>
      </div>
    </div>
  )
}
