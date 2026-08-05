import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Badge from '../ui/Badge.jsx'
import { REPORT_TYPE_LABEL, formatDate } from './constants.js'

/**
 * Template card. Shows template name, report type, version, owner, last
 * used, default badge, and a quick generate action.
 */
export default function TemplateCard({ template, onGenerate, onEdit, onDelete }) {
  const version = template.version || 1

  return (
    <Card className="flex flex-col p-4">
      <div className="flex flex-1 flex-col">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
            {template.name}
          </h3>
          {template.is_default && <Badge tone="primary">Default</Badge>}
        </div>
        <p className="mt-1 text-xs text-[var(--color-muted)]">
          {REPORT_TYPE_LABEL[template.report_type] || template.report_type}
        </p>

        <div className="mt-3 flex flex-col gap-1 text-xs text-[var(--color-muted)]">
          <span>Version: v{version}</span>
          <span>Owner: {template.created_by_name || '—'}</span>
          <span>Last used: {template.updated_at ? formatDate(template.updated_at) : '—'}</span>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button intent="primary" size="sm" className="flex-1" onClick={() => onGenerate(template)}>
          Generate
        </Button>
        <button
          onClick={() => onEdit?.(template)}
          aria-label="Edit template"
          className="rounded-lg border border-[var(--color-border)] p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
            <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
        </button>
        <button
          onClick={() => onDelete?.(template)}
          aria-label="Delete template"
          className="rounded-lg border border-[var(--color-border)] p-2 text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
          </svg>
        </button>
      </div>
    </Card>
  )
}
