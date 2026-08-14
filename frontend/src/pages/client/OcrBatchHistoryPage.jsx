import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'

export default function OcrBatchHistoryPage() {
  const navigate = useNavigate()
  const { batchId } = useParams()

  const [batch, setBatch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadBatch = useCallback(async () => {
    try {
      setLoading(true)
      setError('')

      const response = await apiClient.get(
        `/ocr/history/batches/${batchId}/`,
      )

      const data = response?.data?.data ?? response?.data ?? null
      setBatch(data)
    } catch (err) {
      console.error('Failed to load OCR batch history:', err)

      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to load OCR batch history.',
      )
    } finally {
      setLoading(false)
    }
  }, [batchId])

  useEffect(() => {
    loadBatch()
  }, [loadBatch])

  const formatDate = (value) => {
    if (!value) return '--'

    const date = new Date(value)
    return Number.isNaN(date.getTime())
      ? '--'
      : date.toLocaleString()
  }

  const statusClass = (status) => {
    if (status === 'COMPLETED') return 'text-emerald-600'
    if (status === 'FAILED') return 'text-red-600'
    if (status === 'PARTIAL') return 'text-amber-600'
    if (status === 'PROCESSING') return 'text-blue-600'
    return 'text-[var(--color-muted)]'
  }

  if (loading) {
    return (
      <ClientLayout title="OCR Batch" breadcrumb="OCR Batch">
        <div className="mx-auto w-full max-w-5xl">
          <Card className="p-6 text-sm text-[var(--color-muted)]">
            Loading batch history...
          </Card>
        </div>
      </ClientLayout>
    )
  }

  if (error || !batch) {
    return (
      <ClientLayout title="OCR Batch" breadcrumb="OCR Batch">
        <div className="mx-auto w-full max-w-5xl space-y-4">
          <Card className="p-6">
            <p className="text-sm text-red-600">
              {error || 'Batch not found.'}
            </p>

            <div className="mt-5">
              <Button
                type="button"
                intent="secondary"
                onClick={() => navigate('/app/ocr-test')}
              >
                Back to OCR
              </Button>
            </div>
          </Card>
        </div>
      </ClientLayout>
    )
  }

  const files = batch.files || []

  return (
    <ClientLayout title="OCR Batch" breadcrumb="OCR Batch">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                OCR Batch
              </p>

              <h1 className="mt-1 font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                {batch.source_filename || `${batch.total_files} files`}
              </h1>

              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Uploaded {formatDate(batch.created_at)}
              </p>

              {batch.owner_name && (
                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Owner: {batch.owner_name}
                </p>
              )}
            </div>

            <div className="text-right">
              <p
                className={`text-sm font-semibold uppercase tracking-wide ${statusClass(batch.status)}`}
              >
                {batch.status}
              </p>

              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {batch.completed_files} completed ·{' '}
                {batch.failed_files} failed ·{' '}
                {batch.processing_files} processing
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Files in this batch
              </h2>

              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Select a file to open its saved OCR result.
              </p>
            </div>

            <Button
              type="button"
              intent="secondary"
              onClick={() => navigate('/app/ocr-test')}
            >
              Back to OCR
            </Button>
          </div>

          <div className="divide-y divide-[var(--color-border)] rounded-xl border border-[var(--color-border)]">
            {files.map((file) => (
              <div
                key={file.upload_id}
                className="flex flex-wrap items-center justify-between gap-4 p-4"
              >
                <div className="min-w-0">
                  <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                    {file.filename}
                  </p>

                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    {file.status}
                  </p>
                </div>

                <Button
                  type="button"
                  intent="secondary"
                  disabled={!file.document_id}
                  onClick={() =>
                    file.document_id &&
                    navigate(
                      `/app/ocr-test/history/${file.document_id}`,
                    )
                  }
                >
                  View Result
                </Button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </ClientLayout>
  )
}
