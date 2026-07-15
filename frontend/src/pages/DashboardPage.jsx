import { useState, useEffect } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import KpiCard from '../components/dashboard/KpiCard.jsx'
import Card from '../components/ui/Card.jsx'
import SparklineChart from '../components/dashboard/SparklineChart.jsx'
import TopCustomersBar from '../components/dashboard/TopCustomersBar.jsx'
import ConnectNetSuiteBanner from '../components/dashboard/ConnectNetSuiteBanner.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'
import { dashboardApi } from '../services/dashboard.js'

export default function DashboardPage() {
  const { netSuiteConnected } = useAuth()
  const [summary, setSummary] = useState(null)
  const [recentCustomers, setRecentCustomers] = useState(null)
  const [recentSalesOrders, setRecentSalesOrders] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, customersData, salesOrdersData, invoicesData] = await Promise.all([
        dashboardApi.getSummary(),
        dashboardApi.getRecentCustomers(),
        dashboardApi.getRecentSalesOrders(),
        dashboardApi.getRecentInvoices(),
      ])
      setSummary(summaryData)
      setRecentCustomers(customersData.items || [])
      setRecentSalesOrders(salesOrdersData.items || [])
      setRecentInvoices(invoicesData.items || [])
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const kpis = summary
    ? [
        { id: 'customers', label: 'Customers', value: summary.total_customers, delta: 0, format: 'number' },
        { id: 'employees', label: 'Employees', value: summary.total_employees, delta: 0, format: 'number' },
        { id: 'vendors', label: 'Vendors', value: summary.total_vendors, delta: 0, format: 'number' },
        { id: 'inventory', label: 'Inventory Items', value: summary.total_inventory_items, delta: 0, format: 'number' },
        { id: 'sales-orders', label: 'Sales Orders', value: summary.total_sales_orders, delta: 0, format: 'number' },
        { id: 'purchase-orders', label: 'Purchase Orders', value: summary.total_purchase_orders, delta: 0, format: 'number' },
        { id: 'invoices', label: 'Invoices', value: summary.total_invoices, delta: 0, format: 'number' },
      ]
    : Array.from({ length: 7 }, (_, i) => ({ id: `skeleton-${i}`, label: 'Loading...', value: '--', delta: 0, format: 'number' }))

  const renderRecentSalesOrders = () => {
    if (loading) {
      return (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )
    }
    if (!recentSalesOrders.length) {
      return (
        <EmptyState
          title="No sales orders yet"
          description="Sales orders will appear here once you have data in NetSuite."
        />
      )
    }
    return (
      <div className="flex flex-col gap-2">
        {recentSalesOrders.map((order) => (
          <div key={order.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-sm">
            <span className="font-mono-tabular font-medium text-[var(--color-ink)]">{order.id || order.tranId || order.internalId}</span>
            <span className="text-[var(--color-muted)]">{order.status || 'Open'}</span>
            <span className="font-mono-tabular text-[var(--color-ink-soft)]">{order.total || order.amount ? `$${Number(order.total || order.amount).toLocaleString('en-US')}` : '--'}</span>
          </div>
        ))}
      </div>
    )
  }

  const renderRecentInvoices = () => {
    if (loading) {
      return (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )
    }
    if (!recentInvoices.length) {
      return (
        <EmptyState
          title="No invoices yet"
          description="Invoices will appear here once you have data in NetSuite."
        />
      )
    }
    return (
      <div className="flex flex-col gap-2">
        {recentInvoices.map((invoice) => (
          <div key={invoice.id} className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2 text-sm">
            <span className="font-mono-tabular font-medium text-[var(--color-ink)]">{invoice.id || invoice.tranId || invoice.internalId}</span>
            <span className="text-[var(--color-muted)]">{invoice.status || 'Open'}</span>
            <span className="font-mono-tabular text-[var(--color-ink-soft)]">{invoice.total || invoice.amount ? `$${Number(invoice.total || invoice.amount).toLocaleString('en-US')}` : '--'}</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <DashboardLayout title="Dashboard">
      <div className="flex flex-col gap-6">
        {!netSuiteConnected && <ConnectNetSuiteBanner />}

        {error ? (
          <ErrorState message={error} onRetry={loadDashboard} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map((kpi) => (
                <KpiCard key={kpi.id} {...kpi} />
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              <Card className="p-5 xl:col-span-2">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                    Revenue Trend
                  </h2>
                  {loading ? (
                    <Skeleton className="h-4 w-40" />
                  ) : (
                    <span className="text-xs text-[var(--color-muted)]">Live from NetSuite</span>
                  )}
                </div>
                {loading ? <Skeleton className="h-40 w-full" /> : <SparklineChart data={[]} />}
              </Card>

              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Top Customers
                </h2>
                {loading ? (
                  <div className="flex flex-col gap-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-8 w-full" />
                    ))}
                  </div>
                ) : (
                  <TopCustomersBar customers={recentCustomers?.slice(0, 5) || []} />
                )}
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Recent Sales Orders
                </h2>
                {renderRecentSalesOrders()}
              </Card>
              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Recent Invoices
                </h2>
                {renderRecentInvoices()}
              </Card>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
