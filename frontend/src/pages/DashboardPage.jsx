import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import KpiCard from '../components/dashboard/KpiCard.jsx'
import Card from '../components/ui/Card.jsx'
import SparklineChart from '../components/dashboard/SparklineChart.jsx'
import TopCustomersBar from '../components/dashboard/TopCustomersBar.jsx'
import RecentActivityList from '../components/dashboard/RecentActivityList.jsx'
import ConnectNetSuiteBanner from '../components/dashboard/ConnectNetSuiteBanner.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'
import { kpiSummary, revenueTrend, topCustomers, recentActivity } from '../constants/dummyData.js'

export default function DashboardPage() {
  const { netSuiteConnected } = useAuth()

  return (
    <DashboardLayout title="Dashboard">
      <div className="flex flex-col gap-6">
        {!netSuiteConnected && <ConnectNetSuiteBanner />}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpiSummary.map((kpi) => (
            <KpiCard key={kpi.id} {...kpi} />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="p-5 xl:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Revenue Trend
              </h2>
              <span className="text-xs text-[var(--color-muted)]">Last 12 months · sample data</span>
            </div>
            <SparklineChart data={revenueTrend} />
          </Card>

          <Card className="p-5">
            <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Top Customers
            </h2>
            <TopCustomersBar customers={topCustomers} />
          </Card>
        </div>

        <Card className="p-5">
          <h2 className="mb-2 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            Recent Activity
          </h2>
          <RecentActivityList items={recentActivity} />
        </Card>
      </div>
    </DashboardLayout>
  )
}
