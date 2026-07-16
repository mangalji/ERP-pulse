import { useState, useEffect, useMemo } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import KpiCard from '../components/dashboard/KpiCard.jsx'
import Card from '../components/ui/Card.jsx'
import SparklineChart from '../components/dashboard/SparklineChart.jsx'
import TopCustomersBar from '../components/dashboard/TopCustomersBar.jsx'
import ConnectNetSuiteBanner from '../components/dashboard/ConnectNetSuiteBanner.jsx'
import BusinessActivityTimeline from '../components/dashboard/BusinessActivityTimeline.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'
import { dashboardApi } from '../services/dashboard.js'
import { netsuiteApi } from '../services/netsuite.js'

export default function DashboardPage() {
  const { netSuiteConnected } = useAuth()
  const [summary, setSummary] = useState(null)
  const [recentCustomers, setRecentCustomers] = useState(null)
  const [recentSalesOrders, setRecentSalesOrders] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState(null)
  const [recentPurchaseOrders, setRecentPurchaseOrders] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, customersData, salesOrdersData, invoicesData, purchaseOrdersData] =
        await Promise.all([
          dashboardApi.getSummary(),
          dashboardApi.getRecentCustomers(),
          dashboardApi.getRecentSalesOrders(),
          dashboardApi.getRecentInvoices(),
          netsuiteApi.getPurchaseOrders({ limit: 5 }),
        ])
      setSummary(summaryData)
      setRecentCustomers(customersData.items || [])
      setRecentSalesOrders(salesOrdersData.items || [])
      setRecentInvoices(invoicesData.items || [])
      setRecentPurchaseOrders(purchaseOrdersData.items || [])
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
      return Array.from({ length: 7 }, (_, i) => ({ id: `skeleton-${i}`, label: 'Loading...', value: '--', delta: 0, format: 'number' }))

    return [
      { id: 'customers', label: 'Total Customers', value: summary.total_customers, delta: 0, format: 'number' },
      { id: 'employees', label: 'Total Employees', value: summary.total_employees, delta: 0, format: 'number' },
      { id: 'vendors', label: 'Total Vendors', value: summary.total_vendors, delta: 0, format: 'number' },
      { id: 'inventory', label: 'Total Inventory Items', value: summary.total_inventory_items, delta: 0, format: 'number' },
      { id: 'sales-orders', label: 'Total Sales Orders', value: summary.total_sales_orders, delta: 0, format: 'number' },
      { id: 'purchase-orders', label: 'Total Purchase Orders', value: summary.total_purchase_orders, delta: 0, format: 'number' },
      { id: 'invoices', label: 'Total Invoices', value: summary.total_invoices, delta: 0, format: 'number' },
    ]
  }, [summary])

  const businessActivities = useMemo(() => {
    const activities = []

    recentSalesOrders?.forEach((order) => {
      activities.push({
        id: order.id || order.internalId,
        type: 'sales-order',
        tranId: order.tranId,
        entity: order.entity,
        status: order.status,
        total: order.total || order.amount,
        createdDate: order.createdDate,
        date: order.createdDate || order.date,
      })
    })

    recentPurchaseOrders?.forEach((po) => {
      activities.push({
        id: po.id || po.internalId,
        type: 'purchase-order',
        tranId: po.tranId,
        entity: po.entity,
        status: po.status,
        total: po.total || po.amount,
        createdDate: po.createdDate,
        date: po.createdDate || po.date,
      })
    })

    recentInvoices?.forEach((invoice) => {
      activities.push({
        id: invoice.id || invoice.internalId,
        type: 'invoice',
        tranId: invoice.tranId,
        entity: invoice.entity,
        status: invoice.status,
        total: invoice.total || invoice.amount,
        createdDate: invoice.createdDate,
        date: invoice.createdDate || invoice.date,
      })
    })

    return activities
  }, [recentSalesOrders, recentPurchaseOrders, recentInvoices])

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

              {/* <Card className="p-5">
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
                  // <TopCustomersBar customers={recentCustomers?.slice(0, 5) || []} />
                  <TopCustomersBar customers={[]} />
                )}
              </Card> */}
            </div>

            <Card className="p-5">
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Recent Business Activity
              </h2>
              <BusinessActivityTimeline
                items={businessActivities}
                loading={loading}
                error={null}
                onRetry={loadDashboard}
              />
            </Card>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
