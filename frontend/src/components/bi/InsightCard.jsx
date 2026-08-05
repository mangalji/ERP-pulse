import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import { formatDate } from './format.js'

const PRIORITY_TONE = {
  high: 'negative',
  medium: 'netsuite',
  low: 'neutral',
  unknown: 'neutral',
}

/**
 * InsightCard — renders a single AI-generated executive insight.
 * `insight` is the backend object: { summary, recommendation, priority,
 * confidence, generated_at }.
 */
export default function InsightCard({ insight, loading = false, className = '' }) {
  if (loading) {
    return (
      <Card className={`p-5 ${className}`}>
        <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--color-border)]" />
        <div className="mt-3 h-3 w-full animate-pulse rounded bg-[var(--color-border)]" />
        <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-[var(--color-border)]" />
      </Card>
    )
  }

  const priority = insight?.priority || 'unknown'
  const confidence = insight?.confidence

  return (
    <Card className={`p-5 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
          Executive Insight
        </h3>
        <Badge tone={PRIORITY_TONE[priority] || 'neutral'}>
          {String(priority).charAt(0).toUpperCase() + String(priority).slice(1)} priority
        </Badge>
      </div>

      {insight?.summary && (
        <p className="mt-3 text-sm leading-relaxed text-[var(--color-ink)]">{insight.summary}</p>
      )}

      {insight?.recommendation && (
        <div className="mt-4 rounded-lg bg-[var(--color-primary-soft)] p-3">
          <p className="text-xs font-semibold text-[var(--color-primary-dark)]">Recommendation</p>
          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{insight.recommendation}</p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-4 border-t border-[var(--color-border)] pt-3 text-xs text-[var(--color-muted)]">
        {confidence !== null && confidence !== undefined && (
          <span>
            Confidence: <strong className="text-[var(--color-ink-soft)]">{Math.round(Number(confidence) * 100)}%</strong>
          </span>
        )}
        {insight?.generated_at && <span>Generated {formatDate(insight.generated_at)}</span>}
      </div>
    </Card>
  )
}
