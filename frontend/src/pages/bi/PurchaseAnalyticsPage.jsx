import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function PurchaseAnalyticsPage() {
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
      const res = await biApi.getPurchase(params)
      setData(res)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load purchase analytics')
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
      { label: 'Total Spend', value: data?.total_spend, format: 'currency' },
      { label: 'Purchase Orders', value: data?.total_purchase_orders, format: 'number' },
      { label: 'Avg Order Value', value: data?.average_order_value, format: 'currency' },
      { label: 'Sample Size', value: data?.recent_orders?.length, format: 'number' },
    ],
    [data],
  )

  const vendorList = useMemo(() => {
    const orders = data?.recent_orders || []
    const grouped = {}
    orders.forEach((o) => {
      const name = o.vendor || o.entity || 'Unknown'
      grouped[name] = (grouped[name] || 0) + (Number(o.total) || 0)
    })
    return Object.entries(grouped)
      .map(([name, value]) => ({ label: name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10)
  }, [data])

  return (
    <ClientLayout title="Purchase Analytics">
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
              title="Top Vendors"
              subtitle="By spend"
              loading={loading}
              empty={!loading && vendorList.length === 0}
              onRefresh={load}
            >
              <ProgressList data={vendorList} />
            </ChartCard>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function ProgressList({ data }) {
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
            <div className="h-full rounded-full bg-[var(--color-netsuite)]" style={{ width: `${Math.max(((d.value || 0) / max) * 100, 4)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}
