import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function SalesAnalyticsPage() {
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
      const res = await biApi.getSales(params)
      setData(res)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load sales analytics')
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
      { label: 'Current Revenue', value: data?.current?.revenue, format: 'currency', delta: data?.change_pct },
      { label: 'Previous Revenue', value: data?.previous?.revenue, format: 'currency' },
      { label: 'Sales Orders', value: data?.current?.transaction_count, format: 'number' },
      { label: 'Avg Order Value', value: data?.current?.avg_order_value, format: 'currency' },
    ],
    [data],
  )

  return (
    <ClientLayout title="Sales Analytics">
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

            <ChartCard
              title="Sales Trend"
              subtitle="Revenue over time"
              loading={loading}
              empty={!loading && !(data?.trend?.length)}
              onRefresh={load}
            >
              <BarList data={data?.trend || []} />
            </ChartCard>
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
    <div className="flex h-64 items-end gap-2">
      {data.map((d, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div className="w-full rounded-t bg-[var(--color-primary)]/80" style={{ height: `${Math.max(((d.value || 0) / max) * 100, 4)}%` }} />
          <span className="text-[10px] text-[var(--color-muted)]">{d.label}</span>
        </div>
      ))}
    </div>
  )
}
