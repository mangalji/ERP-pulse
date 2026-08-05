import { useState, useEffect, useCallback, useMemo } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import BiNav from '../../components/bi/BiNav.jsx'
import FilterBar from '../../components/bi/FilterBar.jsx'
import DateRangeSelector from '../../components/bi/DateRangeSelector.jsx'
import InsightCard from '../../components/bi/InsightCard.jsx'
import MetricCard from '../../components/bi/MetricCard.jsx'
import ChartCard from '../../components/bi/ChartCard.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Button from '../../components/ui/Button.jsx'
import { biApi } from '../../services/bi.js'

export default function AiInsightsPage() {
  const [preset, setPreset] = useState('last_30_days')
  const [customRange, setCustomRange] = useState(null)
  const [showCustom, setShowCustom] = useState(false)
  const [insight, setInsight] = useState(null)
  const [kpiSnapshot, setKpiSnapshot] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
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
      const [insightData, summaryData] = await Promise.all([
        biApi.getInsights(params),
        biApi.getSummary(params),
      ])
      setInsight(insightData?.insight || null)
      setKpiSnapshot(insightData?.kpi_snapshot || null)
      setSummary(summaryData)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load AI insights')
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

  const regenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const insightData = await biApi.getInsights(params)
      setInsight(insightData?.insight || null)
      setKpiSnapshot(insightData?.kpi_snapshot || null)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to regenerate insight')
    } finally {
      setGenerating(false)
    }
  }

  const kpiMetrics = useMemo(
    () => [
      { label: 'Sales Revenue', value: summary?.revenue?.sales_revenue, format: 'currency' },
      { label: 'Total Receivables', value: summary?.receivables?.total_receivable, format: 'currency' },
      { label: 'OCR Success', value: summary?.ocr?.success_rate, format: 'percent' },
      { label: 'Sync Success', value: summary?.sync?.success_rate, format: 'percent' },
    ],
    [summary],
  )

  return (
    <ClientLayout title="AI Insights">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <BiNav />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <FilterBar value={preset} onChange={(v) => { setPreset(v); if (v !== 'custom') setShowCustom(false) }} onCustom={() => setShowCustom((prev) => !prev)} />
            <Button size="sm" onClick={regenerate} isLoading={generating} disabled={loading}>
              {generating ? 'Generating…' : 'Regenerate Insight'}
            </Button>
          </div>
          {showCustom && (
            <DateRangeSelector onApply={handleApplyCustom} onCancel={() => setShowCustom(false)} />
          )}
        </div>

        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpiMetrics.map((m) => (
                <MetricCard key={m.label} loading={loading} {...m} />
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <ChartCard
                title="Executive Insight"
                subtitle="AI-generated from summarized KPIs only"
                loading={loading}
                empty={!loading && !insight}
                emptyTitle="No insight generated"
                emptyDescription="Generate an insight for this period."
                onRefresh={load}
              >
                <InsightCard insight={insight} />
              </ChartCard>
              <ChartCard
                title="KPI Snapshot"
                subtitle="Summarized data sent to AI"
                loading={loading}
                empty={!loading && !kpiSnapshot}
                onRefresh={load}
              >
                <KpiSnapshotList data={kpiSnapshot} />
              </ChartCard>
            </div>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function KpiSnapshotList({ data }) {
  if (!data) return null
  const rows = Object.entries(data).filter(([k, v]) => v !== null && v !== undefined)
  return (
    <ul className="divide-y divide-[var(--color-border)]">
      {rows.map(([key, value]) => (
        <li key={key} className="flex items-center justify-between py-2 text-sm">
          <span className="text-[var(--color-ink-soft)]">{key.replace(/_/g, ' ')}</span>
          <span className="font-mono-tabular font-medium text-[var(--color-ink)]">{typeof value === 'number' ? value.toLocaleString() : String(value)}</span>
        </li>
      ))}
    </ul>
  )
}
