import { useState } from 'react'
import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import ErrorState from '../ui/ErrorState.jsx'
import Skeleton from '../ui/Skeleton.jsx'

/**
 * ChartCard — a card shell that wraps a chart with a header, optional
 * badge, loading/empty/error states, and refresh/export/fullscreen actions.
 *
 * `children` is the chart body rendered inside the ResponsiveContainer-less
 * area; the page owns the actual Recharts chart. This keeps the shell
 * generic while every chart still gets the same consistent chrome.
 */
export default function ChartCard({
  title,
  subtitle,
  badge,
  children,
  loading = false,
  empty = false,
  emptyTitle = 'No data yet',
  emptyDescription,
  error,
  onRetry,
  onExport,
  onRefresh,
  actions,
  className = '',
}) {
  const [fullscreen, setFullscreen] = useState(false)

  const renderBody = () => {
    if (loading) return <Skeleton className="h-64 w-full" />
    if (error) return <ErrorState message={error} onRetry={onRetry} />
    if (empty) return <EmptyState title={emptyTitle} description={emptyDescription} />
    return children
  }

  return (
    <Card className={`p-5 ${fullscreen ? 'fixed inset-4 z-50 overflow-auto' : ''} ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-[var(--color-muted)]">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {badge && <Badge tone="netsuite">{badge}</Badge>}
          {onRefresh && (
            <IconButton title="Refresh" onClick={onRefresh}>
              <RefreshIcon />
            </IconButton>
          )}
          {onExport && (
            <IconButton title="Export" onClick={onExport}>
              <ExportIcon />
            </IconButton>
          )}
          <IconButton
            title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            onClick={() => setFullscreen((prev) => !prev)}
          >
            {fullscreen ? <MinimizeIcon /> : <MaximizeIcon />}
          </IconButton>
          {actions}
        </div>
      </div>
      {renderBody()}
    </Card>
  )
}

function IconButton({ title, onClick, children }) {
  return (
    <button
      title={title}
      aria-label={title}
      onClick={onClick}
      className="rounded-md p-1.5 text-[var(--color-muted)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]"
    >
      {children}
    </button>
  )
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" />
    </svg>
  )
}
function ExportIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path d="M12 3v12M8 11l4 4 4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </svg>
  )
}
function MaximizeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
    </svg>
  )
}
function MinimizeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
      <path d="M8 3v3a2 2 0 0 1-2 2H3M16 3v3a2 2 0 0 0 2 2h3M8 21v-3a2 2 0 0 0-2-2H3M16 21v-3a2 2 0 0 1 2-2h3" />
    </svg>
  )
}
