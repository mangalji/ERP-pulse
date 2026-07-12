import Badge from '../ui/Badge.jsx'

const TYPE_TONE = { sync: 'netsuite', ai: 'primary', report: 'positive' }
const TYPE_LABEL = { sync: 'Sync', ai: 'AI', report: 'Report' }

export default function RecentActivityList({ items }) {
  return (
    <ul className="flex flex-col divide-y divide-[var(--color-border)]">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
          <div className="flex items-center gap-3">
            <Badge tone={TYPE_TONE[item.type]}>{TYPE_LABEL[item.type]}</Badge>
            <span className="text-sm text-[var(--color-ink)]">{item.text}</span>
          </div>
          <span className="shrink-0 text-xs text-[var(--color-muted)]">{item.time}</span>
        </li>
      ))}
    </ul>
  )
}
