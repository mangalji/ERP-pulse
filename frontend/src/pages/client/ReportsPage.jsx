import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import { clientApi } from '../../services/client.js'

const MONTH_OPTIONS = [
  { label: '3 months', value: 3 },
  { label: '6 months', value: 6 },
  { label: '12 months', value: 12 },
]

const currencyFormatter = (value) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value || 0)

export default function ReportsPage() {
  const [months, setMonths] = useState(6)
  const [trend, setTrend] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadTrend = async (selectedMonths) => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.getSalesTrend(selectedMonths)
      setTrend(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load sales trend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTrend(months)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [months])

  const chartData = (trend?.trend || []).map((row) => ({
    period: row.period,
    'Sales Orders': row.sales_orders_total,
    'Invoice Revenue': row.invoice_revenue_total,
  }))

  const totals = (trend?.trend || []).reduce(
    (acc, row) => ({
      salesOrders: acc.salesOrders + row.sales_orders_total,
      invoiceRevenue: acc.invoiceRevenue + row.invoice_revenue_total,
    }),
    { salesOrders: 0, invoiceRevenue: 0 },
  )

  return (
    <ClientLayout title="Reports" breadcrumb="Reports">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Sales &amp; Revenue Trend
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Sales order bookings vs. recognized invoice revenue, pulled live from NetSuite.
            </p>
          </div>
          <div className="flex w-fit gap-1 rounded-lg border border-[var(--color-border)] p-1">
            {MONTH_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setMonths(opt.value)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  months === opt.value
                    ? 'bg-[var(--color-primary)] text-white'
                    : 'text-[var(--color-muted)] hover:text-[var(--color-ink)]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {!loading && !error && trend?.trend?.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card className="p-5">
              <p className="text-xs font-medium text-[var(--color-muted)]">Total Sales Orders</p>
              <p className="mt-1 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
                {currencyFormatter(totals.salesOrders)}
              </p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium text-[var(--color-muted)]">Total Invoice Revenue</p>
              <p className="mt-1 font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
                {currencyFormatter(totals.invoiceRevenue)}
              </p>
            </Card>
          </div>
        )}

        <Card className="p-6">
          {loading ? (
            <Skeleton className="h-80 w-full" />
          ) : error ? (
            <ErrorState message={error} onRetry={() => loadTrend(months)} />
          ) : chartData.length === 0 ? (
            <EmptyState
              title="No sales or invoice activity in this period"
              description="Connect a NetSuite account and generate some transactions to see trends here."
            />
          ) : (
            <ResponsiveContainer width="100%" height={360}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--color-muted)" />
                <YAxis tickFormatter={currencyFormatter} tick={{ fontSize: 12 }} stroke="var(--color-muted)" width={80} />
                <Tooltip formatter={(value) => currencyFormatter(value)} />
                <Legend />
                <Bar dataKey="Sales Orders" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Invoice Revenue" fill="var(--color-netsuite)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
