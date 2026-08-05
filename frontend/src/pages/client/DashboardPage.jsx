import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

const FILE_STATUS_TONE = {
  UPLOADED: 'neutral',
  PROCESSING: 'primary',
  EXTRACTED: 'primary',
  REVIEW_REQUIRED: 'netsuite',
  APPROVED: 'positive',
  REJECTED: 'negative',
  READY_FOR_NETSUITE: 'positive',
  FAILED: 'negative',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState([])
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, recentInvoicesData, batchesData] = await Promise.all([
        clientApi.getDashboardSummary(),
        clientApi.getRecentInvoices(),
        clientApi.listInvoiceBatches({ limit: 5 }),
      ])
      setSummary(summaryData)
      setRecentInvoices(recentInvoicesData?.results ?? recentInvoicesData ?? [])
      setBatches(batchesData?.results ?? batchesData ?? [])
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const kpis = useMemo(() => {
    if (!summary)
      return Array.from({ length: 4 }, (_, i) => ({ id: `skeleton-${i}`, label: 'Loading...', value: '--' }))

    const totalFiles = batches.reduce((acc, b) => acc + (b.total_files || 0), 0)
    const processedFiles = batches.reduce((acc, b) => acc + (b.processed_files || 0), 0)
    const failedFiles = batches.reduce((acc, b) => acc + (b.failed_files || 0), 0)

    return [
      { id: 'invoices', label: 'Invoice Batches', value: summary.total_invoices ?? batches.length, icon: 'invoice' },
      { id: 'files', label: 'Total Files', value: totalFiles, icon: 'file' },
      { id: 'processed', label: 'Processed Files', value: processedFiles, icon: 'check' },
      { id: 'failed', label: 'Failed Files', value: failedFiles, icon: 'alert' },
    ]
  }, [summary, batches])

  return (
    <ClientLayout title="Dashboard" breadcrumb="Dashboard">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Welcome back{user?.first_name ? `, ${user.first_name}` : ''}
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            Monitor your invoice processing pipeline and company activity at a glance.
          </p>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={loadDashboard} />
        ) : (
          <>
            {/* KPI cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map((kpi) => (
                <Card key={kpi.id} className="p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-[var(--color-muted)]">{kpi.label}</p>
                      {loading ? (
                        <Skeleton className="mt-2 h-8 w-16" />
                      ) : (
                        <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">{kpi.value}</p>
                      )}
                    </div>
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                      <KpiIcon type={kpi.icon} />
                    </span>
                  </div>
                </Card>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              {/* Recent batches */}
              <Card className="p-5 xl:col-span-2">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                    Recent Invoice Batches
                  </h2>
                  <Link to="/app/invoice-reader" className="text-sm font-medium text-[var(--color-primary)] hover:underline">
                    View all
                  </Link>
                </div>
                {loading ? (
                  <div className="flex flex-col gap-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : batches.length === 0 ? (
                  <EmptyState
                    title="No batches yet"
                    description="Upload your first invoice to get started."
                    actionLabel="Upload invoices"
                    action={() => (window.location.href = '/app/invoice-reader')}
                  />
                ) : (
                  <div className="flex flex-col gap-2">
                    {batches.map((batch) => (
                      <div
                        key={batch.id}
                        className="flex items-center justify-between rounded-lg border border-[var(--color-border)] px-4 py-3"
                      >
                        <div>
                          <p className="text-sm font-medium text-[var(--color-ink)]">
                            Batch #{batch.id}
                          </p>
                          <p className="text-xs text-[var(--color-muted)]">
                            {new Date(batch.created_at).toLocaleString()} · {batch.total_files} files
                          </p>
                        </div>
                        <Badge tone={FILE_STATUS_TONE[batch.status] || 'neutral'}>{batch.status}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Quick actions */}
              <Card className="p-5">
                <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Quick Actions
                </h2>
                <div className="flex flex-col gap-2">
                  <Button intent="primary" size="md" onClick={() => (window.location.href = '/app/invoice-reader')}>
                    Upload Invoices
                  </Button>
                  <Button intent="secondary" size="md" onClick={() => (window.location.href = '/app/ocr-jobs')}>
                    View OCR Jobs
                  </Button>
                  <Button intent="secondary" size="md" onClick={() => (window.location.href = '/app/ai-assistant')}>
                    Ask AI Assistant
                  </Button>
                </div>
              </Card>
            </div>

            {/* Recent invoices from NetSuite */}
            <Card className="p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  Recent Invoices
                </h2>
                <span className="text-xs text-[var(--color-muted)]">Live from NetSuite</span>
              </div>
              {loading ? (
                <Skeleton className="h-32 w-full" />
              ) : recentInvoices.length === 0 ? (
                <EmptyState title="No invoices found" description="Recent invoices from NetSuite will appear here." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                        <th className="pb-2 pr-4 font-medium">Invoice #</th>
                        <th className="pb-2 pr-4 font-medium">Customer</th>
                        <th className="pb-2 pr-4 font-medium">Status</th>
                        <th className="pb-2 pr-4 font-medium">Total</th>
                        <th className="pb-2 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentInvoices.map((inv) => (
                        <tr key={inv.id || inv.internalId} className="border-b border-[var(--color-border)] last:border-0">
                          <td className="py-3 pr-4 font-medium text-[var(--color-ink)]">{inv.tranId || '--'}</td>
                          <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                            {inv.entity && typeof inv.entity === 'object' ? inv.entity.name : '--'}
                          </td>
                          <td className="py-3 pr-4">
                            <Badge tone={inv.status === 'Approved' ? 'positive' : 'neutral'}>{inv.status || '--'}</Badge>
                          </td>
                          <td className="py-3 pr-4 font-mono-tabular text-[var(--color-ink)]">
                            {inv.total != null ? `$${Number(inv.total).toLocaleString('en-US')}` : '--'}
                          </td>
                          <td className="py-3 text-[var(--color-muted)]">{inv.createdDate || inv.date || '--'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </ClientLayout>
  )
}

function KpiIcon({ type }) {
  const common = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: '1.8', className: 'h-5 w-5' }
  if (type === 'invoice') {
    return (
      <svg {...common}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M12 18v-6M9 15l3 3 3-3" />
      </svg>
    )
  }
  if (type === 'file') {
    return (
      <svg {...common}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
      </svg>
    )
  }
  if (type === 'check') {
    return (
      <svg {...common}>
        <path d="M20 6 9 17l-5-5" />
      </svg>
    )
  }
  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4M12 16h.01" />
    </svg>
  )
}
