import { useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import { clientApi } from '../../services/client.js'

function Metric({ label, used, limit, remaining, postedCount }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] p-5">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[var(--color-ink)]">{used}</p>
      <p className="mt-1 text-xs text-[var(--color-muted)]">of {limit} allocated · {remaining} remaining</p>
      <p className="mt-2 text-xs text-[var(--color-muted)]">Posted records: {postedCount ?? 0}</p>
    </div>
  )
}

export default function ProcessingStatusPage() {
  const [usage, setUsage] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    clientApi.getProcessingUsage().then(setUsage).catch((err) => {
      setError(err.payload?.detail || err.payload?.message || err.message || 'Unable to load processing status.')
    })
  }, [])

  return (
    <ClientLayout>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-ink)]">Bill Processing Status</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">Read-only usage allocated by your SuperAdmin.</p>
        </div>
        <Card className="p-6">
          {error && <p className="text-sm text-[var(--color-negative)]">{error}</p>}
          {!error && !usage && <p className="text-sm text-[var(--color-muted)]">Loading...</p>}
          {usage && (
            <>
              <div className="mb-4 grid gap-2 rounded-lg border border-[var(--color-border)] px-4 py-3 text-sm text-[var(--color-muted)] sm:grid-cols-2">
                <span>PDF period: {usage.pdf_allocation_start_date || '—'} to {usage.pdf_allocation_end_date || '—'} · {usage.pdf_allocation_status?.replace('_', ' ') || 'active'}</span>
                <span>Email period: {usage.email_allocation_start_date || '—'} to {usage.email_allocation_end_date || '—'} · {usage.email_allocation_status?.replace('_', ' ') || 'active'}</span>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Metric label="PDF/file pages processed" used={usage.pdf_pages_consumed} limit={usage.pdf_page_limit} remaining={usage.pdf_pages_remaining} postedCount={usage.pdf_posted_count} />
                <Metric label="Email bills processed" used={usage.email_bills_consumed} limit={usage.email_bill_limit} remaining={usage.email_bills_remaining} postedCount={usage.email_posted_count} />
              </div>
            </>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
