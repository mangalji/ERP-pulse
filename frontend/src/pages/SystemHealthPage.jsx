import { useEffect, useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import Badge from '../components/ui/Badge.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import Button from '../components/ui/Button.jsx'
import { monitoringApi } from '../services/monitoring.js'

const STATUS_TONE = {
  healthy: 'positive',
  degraded: 'netsuite',
  down: 'negative',
}

const CHECK_LABEL = {
  database: 'Database',
  email: 'Email (SMTP)',
  netsuite_encryption: 'NetSuite encryption key',
}

// A 403 here just means "you're not staff" — not a real error, so it's
// handled as its own state per-section instead of via ErrorState.
const isForbidden = (err) => (err.response?.status || err.status) === 403

export default function SystemHealthPage() {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [isLoadingHealth, setIsLoadingHealth] = useState(true)

  const [errors, setErrors] = useState(null)
  const [errorsForbidden, setErrorsForbidden] = useState(false)
  const [errorsMessage, setErrorsMessage] = useState('')
  const [isLoadingErrors, setIsLoadingErrors] = useState(true)

  const [usage, setUsage] = useState(null)
  const [usageForbidden, setUsageForbidden] = useState(false)
  const [usageMessage, setUsageMessage] = useState('')
  const [isLoadingUsage, setIsLoadingUsage] = useState(true)

  const loadHealth = async () => {
    setIsLoadingHealth(true)
    setHealthError('')
    try {
      setHealth(await monitoringApi.getHealth())
    } catch (err) {
      setHealthError(err.payload?.message || err.message || 'Failed to load health check')
    } finally {
      setIsLoadingHealth(false)
    }
  }

  const loadErrors = async () => {
    setIsLoadingErrors(true)
    setErrorsForbidden(false)
    setErrorsMessage('')
    try {
      setErrors(await monitoringApi.getErrors(20))
    } catch (err) {
      if (isForbidden(err)) setErrorsForbidden(true)
      else setErrorsMessage(err.payload?.message || err.message || 'Failed to load error log')
    } finally {
      setIsLoadingErrors(false)
    }
  }

  const loadUsage = async () => {
    setIsLoadingUsage(true)
    setUsageForbidden(false)
    setUsageMessage('')
    try {
      setUsage(await monitoringApi.getApiUsage(24))
    } catch (err) {
      if (isForbidden(err)) setUsageForbidden(true)
      else setUsageMessage(err.payload?.message || err.message || 'Failed to load API usage')
    } finally {
      setIsLoadingUsage(false)
    }
  }

  const loadAll = () => {
    loadHealth()
    loadErrors()
    loadUsage()
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <DashboardLayout title="System Health">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
              System Health
            </h2>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Live status of AGSuite ERP's own backend — separate from any individual NetSuite connection.
            </p>
          </div>
          <Button intent="ghost" size="sm" onClick={loadAll}>
            Refresh
          </Button>
        </div>

        {/* Health check */}
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
              Health check
            </h3>
            {health && <Badge tone={STATUS_TONE[health.status] || 'neutral'}>{health.status}</Badge>}
          </div>

          {isLoadingHealth ? (
            <Skeleton className="mt-3 h-16 w-full" />
          ) : healthError ? (
            <p className="mt-3 text-sm text-[var(--color-negative)]">{healthError}</p>
          ) : (
            <div className="mt-3 flex flex-col gap-2">
              {Object.entries(health.checks).map(([key, check]) => (
                <div key={key} className="flex items-center justify-between text-sm">
                  <span className="text-[var(--color-ink-soft)]">{CHECK_LABEL[key] || key}</span>
                  <span className={check.ok ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}>
                    {check.ok ? 'OK' : check.detail}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* API usage */}
        <Card className="p-5">
          <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
            API usage (last 24 hours)
          </h3>
          {isLoadingUsage ? (
            <Skeleton className="mt-3 h-24 w-full" />
          ) : usageForbidden ? (
            <p className="mt-3 text-sm text-[var(--color-muted)]">Admin access required to view this section.</p>
          ) : usageMessage ? (
            <p className="mt-3 text-sm text-[var(--color-negative)]">{usageMessage}</p>
          ) : (
            <>
              <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Requests" value={usage.total_requests} />
                <Stat label="Error rate" value={`${(usage.error_rate * 100).toFixed(1)}%`} />
                <Stat label="Throttled" value={usage.throttled_count} />
                <Stat label="Avg latency" value={`${usage.avg_response_time_ms}ms`} />
              </div>
              {usage.top_endpoints.length > 0 && (
                <div className="mt-4 flex flex-col gap-1.5 border-t border-[var(--color-border)] pt-3">
                  {usage.top_endpoints.map((ep) => (
                    <div key={`${ep.method}-${ep.path}`} className="flex items-center justify-between text-xs">
                      <span className="truncate text-[var(--color-ink-soft)]">
                        {ep.method} {ep.path}
                      </span>
                      <span className="shrink-0 text-[var(--color-muted)]">
                        {ep.request_count} req · {Math.round(ep.avg_response_time_ms)}ms avg
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Card>

        {/* Recent errors */}
        <Card className="p-5">
          <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
            Recent errors
          </h3>
          {isLoadingErrors ? (
            <Skeleton className="mt-3 h-24 w-full" />
          ) : errorsForbidden ? (
            <p className="mt-3 text-sm text-[var(--color-muted)]">Admin access required to view this section.</p>
          ) : errorsMessage ? (
            <p className="mt-3 text-sm text-[var(--color-negative)]">{errorsMessage}</p>
          ) : errors.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-muted)]">No errors logged. All clear.</p>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {errors.map((e) => (
                <div key={e.id} className="border-b border-[var(--color-border)] pb-2 last:border-0 last:pb-0">
                  <div className="flex items-center justify-between text-xs text-[var(--color-muted)]">
                    <span>
                      {e.method} {e.path} · {e.status_code}
                    </span>
                    <span>{new Date(e.created_at).toLocaleString()}</span>
                  </div>
                  <p className="mt-0.5 text-sm text-[var(--color-ink-soft)]">{e.message}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </DashboardLayout>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <p className="text-lg font-semibold text-[var(--color-ink)]">{value}</p>
      <p className="text-xs text-[var(--color-muted)]">{label}</p>
    </div>
  )
}
