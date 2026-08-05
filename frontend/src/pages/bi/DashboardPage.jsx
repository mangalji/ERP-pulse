import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import KpiCard from '../../components/bi/KpiCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import AlertCard from '../../components/bi/AlertCard.jsx'
import InsightCard from '../../components/bi/InsightCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function BIDashboardPage() {
  const [preset, setPreset] = useState('last_30_days')
  const [customRange, setCustomRange] = useState(null)
  const [showCustom, setShowCustom] = useState(false)
  const [summary, setSummary] = useState(null)
  const [sales, setSales] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [insight, setInsight] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const params = useMemo(() => {
    const p = { preset }
    if (preset === 'custom' && customRange) {
      p.start_date = customRange.start
      p.end_date = customRange.end
      delete p.preset
    }
    return p
  }, [preset, customRange])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, salesData, alertsData, insightData] = await Promise.all([
        biApi.getSummary(params),
        biApi.getSales(params),
        biApi.getAlerts(params),
        biApi.getInsights(params),
      ])
      setSummary(summaryData)
      setSales(salesData)
      setAlerts(alertsData?.alerts || [])
      setInsight(insightData?.insight || null)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load executive summary')
    } finally {
      setLoading(false)
    }
  }, [params])

  useEffect(() => {
    load()
  }, [load])

  const handleApplyCustom = (start, end) => {
    setCustomRange({ start, end })
    setPreset('custom')
    setShowCustom(false)
  }

  const currency = summary?.revenue?.currency || 'USD'

  const kpiGroups = useMemo(() => {
    if (!summary) return []
    return [
      {
        label: 'Revenue',
        kpis: [
          { label: 'Sales Revenue', value: summary.revenue?.sales_revenue, format: 'currency', delta: sales?.change_pct },
          { label: 'Invoice Revenue', value: summary.revenue?.invoice_revenue, format: 'currency' },
          { label: 'Sales Orders', value: summary.revenue?.total_sales_orders, format: 'number' },
          { label: 'Invoices', value: summary.revenue?.total_invoices, format: 'number' },
        ],
      },
      {
        label: 'Invoice Pipeline',
        kpis: [
          { label: 'Batches', value: summary.invoice_pipeline?.batches, format: 'number' },
          { label: 'Files', value: summary.invoice_pipeline?.files, format: 'number' },
          { label: 'Approved', value: summary.invoice_pipeline?.approved, format: 'number' },
          { label: 'Failed', value: summary.invoice_pipeline?.failed, format: 'number' },
        ],
      },
      {
        label: 'Platform',
        kpis: [
          { label: 'OCR Success', value: summary.ocr?.success_rate, format: 'percent' },
          { label: 'AI Calls', value: summary.ai?.total_calls, format: 'number' },
          { label: 'AI Success', value: summary.ai?.success_rate, format: 'percent' },
          { label: 'Sync Success', value: summary.sync?.success_rate, format: 'percent' },
        ],
      },
    ]
  }, [summary, sales])

  return (
    <ClientLayout title="Business Intelligence">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <BiNav />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <FilterBar value={preset} onChange={(v) => { setPreset(v); if (v !== 'custom') setShowCustom(false) }} onCustom={() => setShowCustom((prev) => !prev)} />
            <p className="text-xs text-[var(--color-muted)]">
              {summary?.window?.label || 'Loading period…'}
            </p>
          </div>
          {showCustom && (
            <DateRangeSelector onApply={handleApplyCustom} onCancel={() => setShowCustom(false)} />
          )}
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <>
            {kpiGroups.map((section) => (
              <section key={section.label}>
                <h2 className="mb-3 font-[var(--font-display)] text-sm font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  {section.label}
                </h2>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {section.kpis.map((kpi) => (
                    <KpiCard key={kpi.label} loading={loading} currency={currency} {...kpi} />
                  ))}
                </div>
              </section>
            ))}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <ChartCard
                title="Sales Trend"
                subtitle="Period revenue by month"
                loading={loading}
                empty={!loading && !(sales?.trend?.length)}
                onRefresh={load}
              >
                <BarList data={sales?.trend || []} />
              </ChartCard>
              <ChartCard
                title="Executive Insight"
                subtitle="AI-generated summary"
                loading={loading}
                empty={!loading && !insight}
                onRefresh={load}
              >
                <InsightCard insight={insight} />
              </ChartCard>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <ChartCard
                title="Alerts"
                subtitle="Actionable executive alerts"
                loading={loading}
                empty={!loading && alerts.length === 0}
                emptyTitle="No alerts"
                emptyDescription="Everything looks healthy for this period."
                onRefresh={load}
              >
                <div className="flex flex-col gap-3">
                  {alerts.slice(0, 5).map((alert, i) => (
                    <AlertCard key={alert.id || i} alert={alert} />
                  ))}
                </div>
              </ChartCard>
              <ChartCard
                title="Top Customers"
                subtitle="By revenue contribution"
                loading={loading}
                empty={!loading && !(summary?.top_customers?.length)}
                onRefresh={load}
              >
                <TopCustomersList data={summary?.top_customers || []} />
              </ChartCard>
            </div>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function BarList({ data }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map((d) => d.value || 0), 1)
  return (
    <div className="flex h-56 items-end gap-2">
      {data.map((d, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div
            className="w-full rounded-t bg-[var(--color-primary)]/80"
            style={{ height: `${Math.max(((d.value || 0) / max) * 100, 4)}%` }}
            title={d.label}
          />
          <span className="text-[10px] text-[var(--color-muted)]">{d.label}</span>
        </div>
      ))}
    </div>
  )
}

function TopCustomersList({ data }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map((d) => d.value || 0), 1)
  return (
    <ul className="flex flex-col gap-3">
      {data.map((d, i) => (
        <li key={i}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium text-[var(--color-ink)]">{d.label}</span>
            <span className="font-mono-tabular text-xs text-[var(--color-muted)]">{d.value}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-canvas)]">
            <div className="h-full rounded-full bg-[var(--color-primary)]" style={{ width: `${((d.value || 0) / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}
