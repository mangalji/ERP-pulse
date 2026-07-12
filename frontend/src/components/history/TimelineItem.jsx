import Badge from '../ui/Badge.jsx'

const KIND_TONE = { ai: 'primary', report: 'positive' }
const KIND_LABEL = { ai: 'AI Conversation', report: 'Report' }

export default function TimelineItem({ item, isLast }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--color-primary)]" />
        {!isLast && <span className="mt-1 w-px flex-1 bg-[var(--color-border)]" />}
      </div>
      <div className="pb-8">
        <Badge tone={KIND_TONE[item.kind]}>{KIND_LABEL[item.kind]}</Badge>
        <p className="mt-2 text-sm font-medium text-[var(--color-ink)]">{item.title}</p>
        <p className="mt-1 text-xs text-[var(--color-muted)]">{item.date}</p>
      </div>
    </div>
  )
}
