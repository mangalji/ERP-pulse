import Button from '../ui/Button.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import ErrorState from '../ui/ErrorState.jsx'
import Spinner from '../ui/Spinner.jsx'

export default function ConversationList({ conversations, activeId, onSelect, onNew, isLoading, error, onRetry }) {
  return (
    <div className="flex h-full w-64 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="p-3">
        <Button intent="primary" size="sm" className="w-full" onClick={onNew}>
          New Chat
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={onRetry} />
        ) : conversations.length === 0 ? (
          <EmptyState title="No conversations" description="Start a new chat to begin." />
        ) : (
          <div className="flex flex-col gap-0.5">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  activeId === conv.id
                    ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]'
                    : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'
                }`}
              >
                <p className="truncate font-medium">{conv.title || 'New conversation'}</p>
                <p className="truncate text-xs text-[var(--color-muted)]">
                  {new Date(conv.updated_at).toLocaleDateString()}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
