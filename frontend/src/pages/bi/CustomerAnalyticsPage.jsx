import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function CustomerAnalyticsPage() {
  const [preset, setPreset] = useState('last_30_days')
  const [customRange, setCustomRange] = useState(null)
  const [showCustom, setShowCustom] = useState(false)
  const [data, setData] = useState(null)
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
      const res = await biApi.getCustomers(params)
      setData(res)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load customer analytics')
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

  const metrics = useMemo(
    () => [
      { label: 'Total Receivables', value: data?.total_receivables?.total_receivable, format: 'currency' },
      { label: 'Top Customer Segments', value: data?.top_customers?.length, format: 'number' },
      { label: 'Churn Risk', value: data?.churn_risk?.length, format: 'number' },
      { label: 'Revenue Groups', value: data?.revenue_by_customer?.length, format: 'number' },
    ],
    [data],
  )

  const topCustomers = useMemo(() => {
    const list = data?.top_customers || []
    return list.map((c) => ({
      label: c.name || c.customer_name || c.entity || 'Customer',
      value: c.total || c.revenue || c.amount || 0,
    }))
  }, [data])

  const churnList = useMemo(() => {
    const list = data?.churn_risk || []
    return list.map((c) => ({
      label: c.name || c.customer_name || c.entity || 'Customer',
      value: c.risk_score ?? c.churn_score ?? 0,
    }))
  }, [data])

  return (
    <ClientLayout title="Customer Analytics">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <BiNav />
          <FilterBar value={preset} onChange={(v) => { setPreset(v); if (v !== 'custom') setShowCustom(false) }} onCustom={() => setShowCustom((prev) => !prev)} />
          {showCustom && (
            <DateRangeSelector onApply={handleApplyCustom} onCancel={() => setShowCustom(false)} />
          )}
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {metrics.map((m) => (
                <MetricCard key={m.label} loading={loading} {...m} />
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <ChartCard
                title="Top Customers"
                subtitle="By revenue"
                loading={loading}
                empty={!loading && topCustomers.length === 0}
                onRefresh={load}
              >
                <ProgressList data={topCustomers} tone="primary" />
              </ChartCard>
              <ChartCard
                title="Churn Risk"
                subtitle="Customers at risk"
                loading={loading}
                empty={!loading && churnList.length === 0}
                emptyTitle="No churn risk"
                emptyDescription="No customers are currently flagged at risk."
                onRefresh={load}
              >
                <ProgressList data={churnList} tone="netsuite" />
              </ChartCard>
            </div>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function ProgressList({ data, tone = 'primary' }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map((d) => d.value || 0), 1)
  const barColor = tone === 'netsuite' ? 'bg-[var(--color-netsuite)]' : 'bg-[var(--color-primary)]'
  return (
    <ul className="flex flex-col gap-3">
      {data.map((d, i) => (
        <li key={i}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium text-[var(--color-ink)]">{d.label}</span>
            <span className="font-mono-tabular text-xs text-[var(--color-muted)]">{d.value}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-canvas)]">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.max(((d.value || 0) / max) * 100, 4)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}
