import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import { biApi } from '../../services/bi.js'

export default function FinanceAnalyticsPage() {
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
      const res = await biApi.getFinance(params)
      setData(res)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load finance analytics')
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
      { label: 'Revenue', value: data?.revenue, format: 'currency' },
      { label: 'Payables', value: data?.payables, format: 'currency', inverse: true },
      { label: 'Profit', value: data?.profit, format: 'currency' },
      { label: 'Receivables', value: data?.receivables?.total_receivable, format: 'currency', inverse: true },
    ],
    [data],
  )

  const overdueList = useMemo(() => {
    const list = data?.overdue?.overdue_invoices || []
    return list.map((inv) => ({
      label: inv.invoice_number || inv.id,
      value: inv.amount_due || inv.total || 0,
    }))
  }, [data])

  return (
    <ClientLayout title="Finance Analytics">
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
                title="Overdue Invoices"
                subtitle="Aging summary"
                loading={loading}
                empty={!loading && overdueList.length === 0}
                emptyTitle="No overdue"
                emptyDescription="No overdue invoices for this period."
                onRefresh={load}
              >
                <StatusList data={overdueList} />
              </ChartCard>
              <ChartCard
                title="Receivables Summary"
                subtitle="Open balances"
                loading={loading}
                empty={!loading && !(data?.receivables)}
                onRefresh={load}
              >
                <StatusList data={[
                  { label: 'Total Receivable', value: data?.receivables?.total_receivable },
                  { label: 'Currency', value: data?.receivables?.currency || data?.currency },
                ]} />
              </ChartCard>
            </div>
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
