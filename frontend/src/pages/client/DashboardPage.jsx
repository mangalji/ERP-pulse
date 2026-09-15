import { useState, useEffect, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

export default function DashboardPage() {
  const { user } = useAuth()
  const isCompanyAdmin = (user?.roles || []).includes('company_admin')
  const [summary, setSummary] = useState(null)
  const [activity, setActivity] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, activityData] = await Promise.all([
        clientApi.getExecutiveSummary(),
        clientApi.getActivityFeed(10),
      ])
      setSummary(summaryData)
      setActivity(activityData)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

const kpis = useMemo(() => {
  if (!summary)
    return Array.from({ length: 6 }, (_, i) => ({
      id: `skeleton-${i}`,
      label: 'Loading...',
      value: '--',
    }))

  return [
    {
      id: 'total_employees',
      label: 'Total Employees',
      value: summary.total_employees ?? 0,
    },
    {
      id: 'active_employees',
      label: 'Active Employees',
      value: summary.active_employees ?? 0,
    },
    {
      id: 'pending_invitations',
      label: 'Pending Invitations',
      value: summary.pending_invitations ?? 0,
    },
    {
      id: 'connected_netsuite',
      label: 'Connected NetSuite Accounts',
      value: summary.connected_netsuite ?? 0,
    },
    {
      id: 'subscription_plan',
      label: 'Subscription Plan',
      value: summary.subscription_plan ?? '--',
    },
    {
      id: 'plan_expiry',
      label: 'Plan Expiry',
      value: summary.plan_expiry
        ? new Date(summary.plan_expiry).toLocaleDateString()
        : '--',
    },
  ]
}, [summary])
  const activityItems = activity || []

  return (
    <ClientLayout title="Dashboard" breadcrumb="Dashboard">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Welcome back{user?.first_name ? `, ${user.first_name}` : ''}
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            Overview of your company&apos;s employees, invitations, subscription, and NetSuite integration.
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
                      <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">
                        {kpi.value}
                      </p>
                    )}
                  </Card>
                ))}
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
                <EmptyState title="No recent activity" description= {
                  isCompanyAdmin
                    ? 'Recent company activity will appear here.'
                    : 'Your recent activity will appear here.'
                }
                 />
              ) : (
                <div className="flex flex-col gap-2">
                  {activityItems.map((item) => (
                    <div key={item.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Badge tone="neutral">{item.type.replace('_', ' ')}</Badge>
                        <span className="text-sm text-[var(--color-ink)]">{item.text}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                        <span>{item.time ? new Date(item.time).toLocaleString() : '--'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </ClientLayout>
  )
}
