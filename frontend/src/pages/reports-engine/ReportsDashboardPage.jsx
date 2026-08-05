import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import SectionCard from '../../components/reports-engine/SectionCard.jsx'
import ReportCard from '../../components/reports-engine/ReportCard.jsx'
import StatusBadge from '../../components/reports-engine/StatusBadge.jsx'
import { REPORT_TYPES, REPORT_TYPE_LABEL, formatDate } from '../../components/reports-engine/constants.js'
import { reportsEngineApi } from '../../services/reportsEngine.js'

/**
 * Reports Engine dashboard. Shows recent reports, recent downloads,
 * scheduled reports, failed reports, favorite templates, and quick
 * actions.
 */
const QUICK_ACTIONS = [
  { label: 'Generate Report', to: '/app/reports-engine/generate', icon: GenerateIcon },
  { label: 'Scheduled Reports', to: '/app/reports-engine/schedules', icon: ScheduleIcon },
  { label: 'Report History', to: '/app/reports-engine/history', icon: HistoryIcon },
  { label: 'Templates', to: '/app/reports-engine/templates', icon: TemplateIcon },
]

export default function ReportsDashboardPage() {
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [schedules, setSchedules] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [hist, sched, templ] = await Promise.all([
        reportsEngineApi.history.list({ limit: 8, offset: 0 }).catch(() => ({ results: [] })),
        reportsEngineApi.schedules.list({ limit: 6, offset: 0 }).catch(() => ({ results: [] })),
        reportsEngineApi.templates.list({ limit: 6, offset: 0 }).catch(() => ({ results: [] })),
      ])
      setHistory(hist?.results ?? hist ?? [])
      setSchedules(sched?.results ?? sched ?? [])
      setTemplates(templ?.results ?? templ ?? [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const recentDownloads = history.filter((h) => h.download_count > 0).slice(0, 5)
  const failedReports = history.filter((h) => h.status === 'FAILED').slice(0, 5)
  const activeSchedules = schedules.filter((s) => s.is_active).length
  const favoriteTemplates = templates.filter((t) => t.is_default)

  return (
    <ClientLayout title="Reports" breadcrumb="Reports Dashboard">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Reports Engine
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Generate, schedule, and distribute enterprise reports.
            </p>
          </div>
          <Button onClick={() => navigate('/app/reports-engine/generate')}>Generate Report</Button>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {QUICK_ACTIONS.map(({ label, to, icon: Icon }) => (
            <button
              key={to}
              onClick={() => navigate(to)}
              className="flex items-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left transition-colors hover:border-[var(--color-primary)]"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <Icon className="h-4.5 w-4.5" />
              </span>
              <span className="text-sm font-medium text-[var(--color-ink)]">{label}</span>
            </button>
          ))}
        </div>

        {/* Report type cards */}
        <SectionCard title="Start a new report" actions={<Button intent="secondary" size="sm" onClick={() => navigate('/app/reports-engine/generate')}>All reports</Button>}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {REPORT_TYPES.slice(0, 10).map((t) => (
              <ReportCard
                key={t.value}
                label={t.label}
                onGenerate={() => navigate(`/app/reports-engine/generate?type=${t.value}`)}
              />
            ))}
          </div>
        </SectionCard>

        {/* Recent reports + scheduled */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <SectionCard title="Recent Reports" actions={<Button intent="ghost" size="sm" onClick={() => navigate('/app/reports-engine/history')}>View all</Button>}>
            {loading ? (
              <RecentSkeleton />
            ) : history.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--color-muted)]">No reports generated yet.</p>
            ) : (
              <ul className="flex flex-col">
                {history.slice(0, 5).map((h) => (
                  <li key={h.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                        {REPORT_TYPE_LABEL[h.report_type] || h.report_type}
                      </p>
                      <p className="text-xs text-[var(--color-muted)]">
                        {formatDate(h.generated_at)} · {h.format}
                      </p>
                    </div>
                    <StatusBadge status={h.status} />
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title={`Scheduled Reports (${activeSchedules} active)`} actions={<Button intent="ghost" size="sm" onClick={() => navigate('/app/reports-engine/schedules')}>View all</Button>}>
            {loading ? (
              <RecentSkeleton />
            ) : schedules.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--color-muted)]">No schedules yet.</p>
            ) : (
              <ul className="flex flex-col">
                {schedules.slice(0, 5).map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">{s.name}</p>
                      <p className="text-xs text-[var(--color-muted)]">
                        {s.frequency} · {REPORT_TYPE_LABEL[s.report_type] || s.report_type}
                      </p>
                    </div>
                    <StatusBadge status={s.is_active ? 'PROCESSING' : 'EXPIRED'} />
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        {/* Recent downloads + failed + favorites */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <SectionCard title="Recent Downloads">
            {loading ? (
              <RecentSkeleton />
            ) : recentDownloads.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--color-muted)]">No downloads yet.</p>
            ) : (
              <ul className="flex flex-col">
                {recentDownloads.map((h) => (
                  <li key={h.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                        {REPORT_TYPE_LABEL[h.report_type] || h.report_type}
                      </p>
                      <p className="text-xs text-[var(--color-muted)]">{h.download_count} downloads</p>
                    </div>
                    <span className="text-xs text-[var(--color-muted)]">{formatDate(h.generated_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Failed Reports">
            {loading ? (
              <RecentSkeleton />
            ) : failedReports.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--color-muted)]">No failed reports.</p>
            ) : (
              <ul className="flex flex-col">
                {failedReports.map((h) => (
                  <li key={h.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                        {REPORT_TYPE_LABEL[h.report_type] || h.report_type}
                      </p>
                      <p className="truncate text-xs text-[var(--color-muted)]">{h.error_message || 'See history'}</p>
                    </div>
                    <StatusBadge status="FAILED" />
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Favorite Templates">
            {loading ? (
              <RecentSkeleton />
            ) : favoriteTemplates.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--color-muted)]">No favorite templates.</p>
            ) : (
              <ul className="flex flex-col">
                {favoriteTemplates.slice(0, 5).map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--color-ink)]">{t.name}</p>
                      <p className="text-xs text-[var(--color-muted)]">
                        {REPORT_TYPE_LABEL[t.report_type] || t.report_type}
                      </p>
                    </div>
                    <Button intent="secondary" size="sm" onClick={() => navigate(`/app/reports-engine/generate?type=${t.report_type}`)}>
                      Generate
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      </div>
    </ClientLayout>
  )
}

function RecentSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-lg bg-[var(--color-canvas)]" />
      ))}
    </div>
  )
}

function GenerateIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M12 18v-4M10 16h4" />
    </svg>
  )
}
function ScheduleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
      <path d="M12 15l2 2 3-3" />
    </svg>
  )
}
function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  )
}
function TemplateIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  )
}
