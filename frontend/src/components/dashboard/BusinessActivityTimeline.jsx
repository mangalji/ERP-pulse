import { useMemo } from 'react'
import Badge from '../ui/Badge.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import ErrorState from '../ui/ErrorState.jsx'

const TYPE_TONE = {
  'sales-order': 'primary',
  'purchase-order': 'netsuite',
  invoice: 'positive',
}

const TYPE_LABEL = {
  'sales-order': 'Sales Order',
  'purchase-order': 'Purchase Order',
  invoice: 'Invoice',
}

export default function BusinessActivityTimeline({ items = [], loading, error, onRetry }) {
  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      const dateA = new Date(a.date || a.createdDate || 0)
      const dateB = new Date(b.date || b.createdDate || 0)
      return dateB - dateA
    })
  }, [items])

  if (error) {
    return <ErrorState message={error} onRetry={onRetry} />
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
            <div className="flex-1">
              <Skeleton className="h-4 w-32 mb-2" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!sorted.length) {
    return (
      <EmptyState
        title="No recent activity"
        description="Sales orders, purchase orders, and invoices will appear here."
      />
    )
  }

  return (
    <div className="relative flex flex-col gap-0">
      <div className="absolute inset-x-0 top-0 bottom-0 ml-4 w-px bg-[var(--color-border)]" aria-hidden="true" />
      <ul className="flex flex-col">
        {sorted.map((item, idx) => {
          const tone = TYPE_TONE[item.type] || 'neutral'
          const label = TYPE_LABEL[item.type] || item.type
          const date = item.date || item.createdDate
          const title = item.tranId || item.title || item.id
          const subtitle = item.entity?.name || item.entity || item.status || ''
          const amount = item.total || item.amount

          return (
            <li key={item.id || `${item.type}-${idx}`} className="relative flex gap-4 pb-4 last:pb-0">
              <span
                className={`relative z-10 mt-1 h-8 w-8 shrink-0 rounded-full border-2 border-[var(--color-surface)] flex items-center justify-center ${
                  tone === 'primary'
                    ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary)]'
                    : tone === 'netsuite'
                      ? 'bg-[var(--color-netsuite-soft)] text-[var(--color-netsuite)]'
                      : tone === 'positive'
                        ? 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]'
                        : 'bg-[var(--color-canvas)] text-[var(--color-ink-soft)]'
                }`}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                  {item.type === 'sales-order' && (
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  )}
                  {item.type === 'purchase-order' && (
                    <circle cx="9" cy="21" r="1" />
                  )}
                  {item.type === 'invoice' && (
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  )}
                </svg>
              </span>
              <div className="flex flex-1 flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--color-ink)]">{title}</span>
                  <Badge tone={tone}>{label}</Badge>
                </div>
                <span className="text-sm text-[var(--color-muted)]">{subtitle}</span>
                <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                  {date && <span>{new Date(date).toLocaleDateString()}</span>}
                  {amount != null && (
                    <span className="font-mono-tabular">${Number(amount).toLocaleString('en-US')}</span>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
