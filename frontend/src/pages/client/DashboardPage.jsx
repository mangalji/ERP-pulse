import { useState, useEffect, useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

const CHART_COLORS = [
  'var(--color-primary)',
  'var(--color-positive)',
  'var(--color-negative)',
  'var(--color-netsuite)',
  'var(--color-warning)',
  'var(--color-muted)',
]

const QUICK_ACTIONS = [
  { label: 'Upload Invoice', href: '/app/invoice-reader', intent: 'primary' },
  { label: 'Add Employee', href: '/app/employees', intent: 'secondary' },
  { label: 'Invite Employee', href: '/app/employees', intent: 'secondary' },
  { label: 'Connect NetSuite', href: '/app/integrations/netsuite', intent: 'secondary' },
  { label: 'Generate Report', href: '/app/reports', intent: 'secondary' },
  { label: 'Open AI Assistant', href: '/app/ai-assistant', intent: 'secondary' },
]

const ACTIVITY_TONE = {
  employee: 'primary',
  invoice: 'positive',
  ocr: 'netsuite',
  report: 'warning',
  ai: 'primary',
  netsuite: 'netsuite',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [charts, setCharts] = useState(null)
  const [activity, setActivity] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, chartsData, activityData] = await Promise.all([
        clientApi.getExecutiveSummary(),
        clientApi.getExecutiveCharts(),
        clientApi.getActivityFeed(10),
      ])
      setSummary(summaryData)
      setCharts(chartsData)
      setActivity(activityData)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const kpis = useMemo(() => {
    if (!summary)
      return Array.from({ length: 16 }, (_, i) => ({ id: `skeleton-${i}`, label: 'Loading...', value: '--' }))

      return [
        { id: 'total_employees', label: 'Total Employees', value: summary.total_employees ?? 0 },
        { id: 'active_employees', label: 'Active Employees', value: summary.active_employees ?? 0 },
        { id: 'pending_invitations', label: 'Pending Invitations', value: summary.pending_invitations ?? 0 },
        { id: 'connected_netsuite', label: 'Connected NetSuite Accounts', value: summary.connected_netsuite ?? 0 },
        { id: 'invoices_uploaded', label: 'Invoices Uploaded', value: summary.invoices_uploaded ?? 0 },
        { id: 'invoices_pending_review', label: 'Invoices Pending Review', value: summary.invoices_pending_review ?? 0 },
        { id: 'approved_invoices', label: 'Approved Invoices', value: summary.approved_invoices ?? 0 },
        { id: 'ocr_failed', label: 'OCR Failed', value: summary.ocr_failed ?? 0 },
        { id: 'reports_generated', label: 'Reports Generated', value: summary.reports_generated ?? 0 },
        { id: 'ai_requests', label: 'AI Requests', value: summary.ai_requests ?? 0 },
        { id: 'subscription_plan', label: 'Subscription Plan', value: summary.subscription_plan ?? '--' },
        { id: 'plan_expiry', label: 'Plan Expiry', value: summary.plan_expiry ? new Date(summary.plan_expiry).toLocaleDateString() : '--' },
        { id: 'storage_used_mb', label: 'Storage Used', value: summary.storage_used_mb != null ? `${summary.storage_used_mb} MB` : '--' },
        { id: 'ai_credits', label: 'AI Credits', value: summary.ai_credits ?? 0 },
        { id: 'ocr_credits', label: 'OCR Credits', value: summary.ocr_credits ?? 0 },
        { id: 'modules_enabled', label: 'Modules Enabled', value: summary.modules_enabled ?? 0 },
      ]
  }, [summary])

  const activityItems = useMemo(() => {
    if (!activity) return []
    const items = []
    activity.recent_employees?.forEach((e) => {
      items.push({ id: `emp-${e.id}`, type: 'employee', text: `${e.first_name} ${e.last_name} (${e.email})`, time: e.created_at })
    })
    activity.recent_invoices?.forEach((inv) => {
      items.push({ id: `inv-${inv.id}`, type: 'invoice', text: `${inv.original_filename || 'Invoice'}`, time: inv.created_at, meta: inv.status })
    })
    activity.recent_ocr_jobs?.forEach((job) => {
      items.push({ id: `ocr-${job.id}`, type: 'ocr', text: `Batch #${job.id} — ${job.total_files} files`, time: job.created_at, meta: job.status })
    })
    activity.recent_reports?.forEach((rpt) => {
      items.push({ id: `rpt-${rpt.id}`, type: 'report', text: `${rpt.report_type || 'Report'}`, time: rpt.generated_at, meta: rpt.status })
    })
    activity.recent_ai_conversations?.forEach((conv) => {
      items.push({ id: `ai-${conv.id}`, type: 'ai', text: conv.title || 'AI Conversation', time: conv.updated_at })
    })
    activity.recent_netsuite_syncs?.forEach((sync) => {
      items.push({ id: `ns-${sync.id}`, type: 'netsuite', text: `${sync.client_name || sync.netsuite_account_id || 'Connection'}`, time: sync.last_synced_at, meta: sync.status })
    })
    return items.sort((a, b) => new Date(b.time) - new Date(a.time)).slice(0, 20)
  }, [activity])

  return (
    <ClientLayout title="Dashboard" breadcrumb="Dashboard">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Welcome back{user?.first_name ? `, ${user.first_name}` : ''}
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            Executive overview of your company&apos;s employees, invoices, AI activity, and NetSuite integration.
          </p>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={loadDashboard} />
        ) : (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map((kpi) => (
                <Card key={kpi.id} className="p-5">
                  <p className="text-sm text-[var(--color-muted)]">{kpi.label}</p>
                  {loading ? (
                    <Skeleton className="mt-2 h-8 w-20" />
                  ) : (
                    <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">{kpi.value}</p>
                  )}
                </Card>
              ))}
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Invoices by Status</h2>
                {loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : charts?.invoice_charts?.by_status?.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie data={charts.invoice_charts.by_status} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={80} label>
                        {charts.invoice_charts.by_status.map((entry, index) => (
                          <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No data" description="Invoice status breakdown will appear here." />
                )}
              </Card>

              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Invoices by Month</h2>
                {loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : charts?.invoice_charts?.by_month?.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={charts.invoice_charts.by_month}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <Tooltip />
                      <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No data" description="Monthly invoice volume will appear here." />
                )}
              </Card>

              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">OCR Success vs Failed</h2>
                {loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : charts?.invoice_charts?.ocr_success_vs_failed?.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie data={charts.invoice_charts.ocr_success_vs_failed} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={80} label>
                        {charts.invoice_charts.ocr_success_vs_failed.map((entry, index) => (
                          <Cell key={index} fill={entry.status === 'Success' ? 'var(--color-positive)' : 'var(--color-negative)'} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No data" description="OCR success rate will appear here." />
                )}
              </Card>

              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Employee Growth</h2>
                {loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : charts?.employee_growth?.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={charts.employee_growth}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <Tooltip />
                      <Bar dataKey="count" fill="var(--color-netsuite)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No data" description="Employee growth will appear here." />
                )}
              </Card>

              <Card className="p-5 xl:col-span-2">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">AI Usage</h2>
                {loading ? (
                  <Skeleton className="h-64 w-full" />
                ) : charts?.ai_usage?.length ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={charts.ai_usage}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                      <Tooltip />
                      <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState title="No data" description="AI usage trends will appear here." />
                )}
              </Card>
            </div>

            {/* Recent Activity */}
            <Card className="p-5">
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Recent Activity</h2>
              {loading ? (
                <div className="flex flex-col gap-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : activityItems.length === 0 ? (
                <EmptyState title="No recent activity" description="Recent employees, invoices, and syncs will appear here." />
              ) : (
                <div className="flex flex-col gap-2">
                  {activityItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Badge tone={ACTIVITY_TONE[item.type] || 'neutral'}>{item.type.replace('_', ' ')}</Badge>
                        <span className="text-sm text-[var(--color-ink)]">{item.text}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                        {item.meta && <span>{item.meta}</span>}
                        <span>{item.time ? new Date(item.time).toLocaleString() : '--'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Quick Actions */}
            <Card className="p-5">
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Quick Actions</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {QUICK_ACTIONS.map((action) => (
                  <Button
                    key={action.label}
                    intent={action.intent}
                    size="md"
                    onClick={() => (window.location.href = action.href)}
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </ClientLayout>
  )
}
