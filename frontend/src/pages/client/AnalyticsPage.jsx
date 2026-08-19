import { useState, useEffect, useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import { clientApi } from '../../services/client.js'

const currencyFormatter = (value) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value || 0)

export default function AnalyticsPage() {
  const [summary, setSummary] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [netsuiteAvailable, setNetsuiteAvailable] = useState(true)

  const loadAnalytics = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, invoicesData] = await Promise.all([
        clientApi.getDashboardSummary(),
        clientApi.getRecentInvoices(),
      ])

      const available = summaryData.netsuite_available != false
      setNetsuiteAvailable(available)

      if (!available) {
        setSummary(summaryData)
        setRecentInvoices([])
        return
      }
      setSummary(summaryData)
      setRecentInvoices(invoicesData?.results ?? invoicesData ?? [])
    } catch (err) {
      setError(
        err.payload?.message || 
          err.message || 
            'Failed to load analytics',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnalytics()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const invoiceTrend = useMemo(() => {
    const byDate = {}
    recentInvoices.forEach((inv) => {
      const date = inv.createdDate || inv.date
      if (!date) return
      const key = String(date).slice(0, 10)
      const total = Number(inv.total || inv.amount || 0)
      byDate[key] = (byDate[key] || 0) + total
    })
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, total]) => ({ date, total }))
  }, [recentInvoices])

  const totalRevenue = useMemo(
    () => recentInvoices.reduce((acc, inv) => acc + Number(inv.total || inv.amount || 0), 0),
    [recentInvoices],
  )

  const kpis = useMemo(() => {
    if (!summary)
      return Array.from({ length: 4 }, (_, i) => ({ id: `skeleton-${i}`, label: 'Loading...', value: '--' }))
    return [
      { id: 'invoices', label: 'NetSuite Invoices', value: summary.total_invoices ?? recentInvoices.length },
      { id: 'revenue', label: 'Invoice Revenue', value: currencyFormatter(totalRevenue) },
      { id: 'employees', label: 'Employees', value: summary.total_employees ?? '--' },
      { id: 'activity', label: 'Recent Invoices', value: recentInvoices.length },
    ]
  }, [summary, recentInvoices, totalRevenue])

  return (
    <ClientLayout title="Analytics" breadcrumb="Analytics">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Company Analytics
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            High-level insights derived from your NetSuite data and invoice processing pipeline.
          </p>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={loadAnalytics} />
        ) : !loading && !netsuiteAvailable ? (
          <Card className="p-8">
            <div className="flex flex-col items-center justify-center text-center">
              <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                NetSuite data is not available
              </h2>
        
              <p className="mt-2 max-w-md text-sm text-[var(--color-muted)]">
                Connect your NetSuite account to view analytics and invoice data.
              </p>
            </div>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map((kpi) => (
                <Card key={kpi.id} className="p-5">
                  <p className="text-sm text-[var(--color-muted)]">{kpi.label}</p>
                  {loading ? (
                    <Skeleton className="mt-2 h-8 w-16" />
                  ) : (
                    <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">{kpi.value}</p>
                  )}
                </Card>
              ))}
            </div>

            <Card className="p-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Invoice Revenue Trend
                </h2>
                {netsuiteAvailable && (
                  <Badge tone="netsuite">Live from NetSuite</Badge>
                )}
              </div>
              {loading ? (
                <Skeleton className="h-72 w-full" />
              ) : invoiceTrend.length === 0 ? (
                <EmptyState
                  title="No invoice data yet"
                  description="Invoice revenue by day will appear here once NetSuite invoices are available."
                />
              ) : (
                <ResponsiveContainer width="100%" height={320}>
                  <AreaChart data={invoiceTrend}>
                    <defs>
                      <linearGradient id="revGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                    <YAxis tickFormatter={currencyFormatter} tick={{ fontSize: 11 }} stroke="var(--color-muted)" width={80} />
                    <Tooltip formatter={(value) => currencyFormatter(value)} />
                    <Area type="monotone" dataKey="total" stroke="var(--color-primary)" fill="url(#revGradient)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>
          </>
        )}
      </div>
    </ClientLayout>
  )
}
