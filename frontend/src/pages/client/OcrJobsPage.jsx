import { useState, useCallback, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import { clientApi } from '../../services/client.js'

const STATUS_TONE = {
  UPLOADING: 'neutral',
  PROCESSING: 'primary',
  COMPLETED: 'positive',
  FAILED: 'negative',
}

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

const FILE_STATUS_LABEL = {
  UPLOADED: 'Uploaded',
  PROCESSING: 'Processing',
  EXTRACTED: 'Extracted',
  REVIEW_REQUIRED: 'Review Required',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  READY_FOR_NETSUITE: 'Ready for NetSuite',
  FAILED: 'Failed',
}

export default function OcrJobsPage() {
  const [batches, setBatches] = useState([])
  const [selectedBatch, setSelectedBatch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadBatches = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.listInvoiceBatches({ limit: 50 })
      const list = data?.results ?? data ?? []
      setBatches(list)
      setSelectedBatch((prev) => prev || list[0] || null)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load OCR jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBatches()
  }, [loadBatches])

  const counts = batches.reduce(
    (acc, b) => {
      acc.total += b.total_files || 0
      acc.completed += b.processed_files || 0
      acc.failed += b.failed_files || 0
      return acc
    },
    { total: 0, completed: 0, failed: 0 },
  )

  return (
    <ClientLayout title="OCR Jobs" breadcrumb="OCR Jobs">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            OCR Processing
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            Track the OCR and AI extraction pipeline across all your uploaded invoice batches.
          </p>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <p className="text-sm text-[var(--color-muted)]">Total Files</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">{counts.total}</p>
          </Card>
          <Card className="p-5">
            <p className="text-sm text-[var(--color-muted)]">Processed</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--color-positive)]">{counts.completed}</p>
          </Card>
          <Card className="p-5">
            <p className="text-sm text-[var(--color-muted)]">Failed</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--color-negative)]">{counts.failed}</p>
          </Card>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={loadBatches} />
        ) : loading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : batches.length === 0 ? (
          <EmptyState
            title="No OCR jobs yet"
            description="Upload invoices in the Invoice Reader to start the OCR pipeline."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            {/* Batch list */}
            <Card className="p-4 xl:col-span-1">
              <h2 className="mb-3 px-1 font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
                Batches
              </h2>
              <div className="flex flex-col gap-1">
                {batches.map((batch) => (
                  <button
                    key={batch.id}
                    onClick={() => setSelectedBatch(batch)}
                    className={`rounded-lg px-3 py-2.5 text-left transition-colors ${
                      selectedBatch?.id === batch.id
                        ? 'bg-[var(--color-primary-soft)]'
                        : 'hover:bg-[var(--color-canvas)]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-[var(--color-ink)]">Batch #{batch.id}</p>
                      <Badge tone={STATUS_TONE[batch.status] || 'neutral'}>{batch.status}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                      {new Date(batch.created_at).toLocaleString()} · {batch.total_files || 0} files
                    </p>
                  </button>
                ))}
              </div>
            </Card>

            {/* Selected batch details */}
            <Card className="p-6 xl:col-span-2">
              {selectedBatch ? (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                        Batch #{selectedBatch.id}
                      </h2>
                      <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                        Uploaded {new Date(selectedBatch.created_at).toLocaleString()} ·{' '}
                        {selectedBatch.processed_files || 0}/{selectedBatch.total_files || 0} processed
                      </p>
                    </div>
                    <Badge tone={STATUS_TONE[selectedBatch.status] || 'neutral'}>{selectedBatch.status}</Badge>
                  </div>

                  {selectedBatch.files?.length === 0 ? (
                    <EmptyState title="No files in this batch" />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                            <th className="pb-2 pr-4 font-medium">Filename</th>
                            <th className="pb-2 pr-4 font-medium">Status</th>
                            <th className="pb-2 pr-4 font-medium">Confidence</th>
                            <th className="pb-2 font-medium">Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedBatch.files || []).map((file) => (
                            <tr key={file.id} className="border-b border-[var(--color-border)] last:border-0">
                              <td className="py-3 pr-4 font-medium text-[var(--color-ink)]">
                                {file.original_filename}
                              </td>
                              <td className="py-3 pr-4">
                                <Badge tone={FILE_STATUS_TONE[file.status] || 'neutral'}>
                                  {FILE_STATUS_LABEL[file.status] || file.status}
                                </Badge>
                              </td>
                              <td className="py-3 pr-4 font-mono-tabular text-[var(--color-ink-soft)]">
                                {file.extraction?.confidence_score != null
                                  ? `${Math.round(file.extraction.confidence_score * 100)}%`
                                  : '—'}
                              </td>
                              <td className="py-3 text-[var(--color-muted)]">
                                {file.processing_time != null ? `${file.processing_time.toFixed(1)}s` : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              ) : (
                <EmptyState title="Select a batch" description="Choose a batch from the list to view its OCR details." />
              )}
            </Card>
          </div>
        )}
      </div>
    </ClientLayout>
  )
}
