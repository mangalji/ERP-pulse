import Card from '../ui/Card.jsx'

export default function ModuleGrid({ modules, onToggle, enabledIds = [] }) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Modules</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {modules.map((mod) => {
          const enabled = enabledIds.includes(mod.id)
          return (
            <div
              key={mod.id}
              className={`flex items-center justify-between rounded-lg border p-3 ${
                enabled ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]' : 'border-[var(--color-border)]'
              }`}
            >
              <div>
                <p className="text-sm font-medium text-[var(--color-ink)]">{mod.display_name || mod.name}</p>
                <p className="text-xs text-[var(--color-muted)]">{mod.code}</p>
              </div>
              {onToggle && (
                <button
                  onClick={() => onToggle(mod.id)}
                  className={`rounded-md px-2 py-1 text-xs font-medium ${
                    enabled
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-canvas)] text-[var(--color-ink-soft)] hover:bg-[var(--color-border)]'
                  }`}
                >
                  {enabled ? 'Enabled' : 'Disabled'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
