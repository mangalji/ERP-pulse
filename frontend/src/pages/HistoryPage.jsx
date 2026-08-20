import { useEffect, useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import { authApi } from '../services/auth.js'

const formatDateTime = (isoString) =>
  new Date(isoString).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })

export default function HistoryPage() {
  const [activities, setActivities] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadHistory = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await authApi.getLoginHistory()
      setActivities(data.results || data || [])
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load login history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  return (
    <DashboardLayout title="History">
      <div className="max-w-2xl">
        <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
          Login Activity
        </h2>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          Recent sign-ins to your AGSuite ERP account, most recent first.
        </p>

        <Card className="mt-4 p-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={loadHistory} />
          ) : activities.length === 0 ? (
            <EmptyState title="No login activity yet" description="Your sign-ins will show up here." />
          ) : (
            <div className="flex flex-col">
              {activities.map((activity, index) => (
                <div
                  key={activity.id}
                  className={`flex items-center justify-between gap-4 py-3 ${
                    index !== activities.length - 1 ? 'border-b border-[var(--color-border)]' : ''
                  }`}
                >
                  <div>
                    <p className="text-sm font-medium text-[var(--color-ink)]">
                      {formatDateTime(activity.created_at)}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                      {activity.ip_address || 'Unknown IP'}
                    </p>
                  </div>
                  {activity.user_agent && (
                    <p className="max-w-[50%] truncate text-right text-xs text-[var(--color-muted)]" title={activity.user_agent}>
                      {activity.user_agent}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </DashboardLayout>
  )
}
