import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function InventoryAnalyticsPage() {
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
      const res = await biApi.getInventory(params)
      setData(res)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load inventory analytics')
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
      { label: 'Inventory Value', value: data?.inventory_value, format: 'currency' },
      { label: 'Total Items', value: data?.total_items, format: 'number' },
      { label: 'Low Stock Items', value: data?.low_stock_items?.length, format: 'number' },
      { label: 'Sample Items', value: data?.items?.length, format: 'number' },
    ],
    [data],
  )

  const lowStockList = useMemo(() => {
    const list = data?.low_stock_items || []
    return list.map((item) => ({
      label: item.item_name || item.itemId || item.internalId || item.id || 'Item',
      value: item.available || item.currentQty || item.quantity_on_hand || 0,
    }))
  }, [data])

  return (
    <ClientLayout title="Inventory Analytics">
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
              title="Low Stock Items"
              subtitle="Items below reorder point"
              loading={loading}
              empty={!loading && lowStockList.length === 0}
              emptyTitle="No low stock"
              emptyDescription="All items are above reorder levels."
              onRefresh={load}
            >
              <StatusList data={lowStockList} />
            </ChartCard>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function StatusList({ data }) {
  if (!data || data.length === 0) return null
  return (
    <ul className="divide-y divide-[var(--color-border)]">
      {data.map((d, i) => (
        <li key={i} className="flex items-center justify-between py-2.5 text-sm">
          <span className="text-[var(--color-ink-soft)]">{d.label}</span>
          <span className="font-mono-tabular font-medium text-[var(--color-ink)]">{d.value}</span>
        </li>
      ))}
    </ul>
  )
}
