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
      return data
    } catch (err) {
      console.error('Failed to load OCR batch history:', err)

      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to load OCR batch history.',
      )
      return null
    } finally {
      setLoading(false)
    }
  }, [batchId])

  useEffect(() => {
    loadBatch()
  }, [loadBatch])

  useEffect(() => {
    let cancelled = false
    const startedAt = Date.now()
    const maxPollingMs = 30 * 60 * 1000

    const poll = async () => {
      while (!cancelled && Date.now() - startedAt < maxPollingMs) {
        const data = await loadBatch()

        if (cancelled || !data) return

        const files = Array.isArray(data.files) ? data.files : []
        const completed = Number(data.completed_files ?? 0)
        const failed = Number(data.failed_files ?? 0)
        const total = Number(data.total_files ?? files.length)
        const terminal =
          total > 0 &&
          completed + failed === total &&
          files.every((file) =>
            ['COMPLETED', 'FAILED'].includes(file.status),
          )

        const batchTerminal = ['COMPLETED', 'FAILED', 'PARTIAL'].includes(
          String(data.status || '').toUpperCase(),
        )

        if (terminal || batchTerminal) return

        await new Promise((resolve) => setTimeout(resolve, 1500))
      }
    }

    poll().catch((err) => {
      if (!cancelled) {
        console.error('OCR batch polling failed:', err)
      }
    })

    return () => {
      cancelled = true
    }
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
    if (status === 'RETRYING') return 'text-amber-600'
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

  const totalFiles = Number(batch.total_files ?? files.length)
  const completedFiles = Number(batch.completed_files ?? 0)
  const failedFiles = Number(batch.failed_files ?? 0)
  const processingFiles = Number(batch.processing_files ?? 0)
  const queuedFiles = Number(batch.queued_files ?? 0)

  const effectiveStatus =
    totalFiles > 0 && completedFiles === totalFiles
      ? 'COMPLETED'
      : totalFiles > 0 && failedFiles === totalFiles
        ? 'FAILED'
        : totalFiles > 0 &&
            completedFiles + failedFiles === totalFiles &&
            failedFiles > 0
          ? 'PARTIAL'
          : processingFiles > 0
            ? 'PROCESSING'
            : queuedFiles > 0
              ? 'RETRYING'
              : String(batch.status || 'PROCESSING').toUpperCase()

  const isTerminal = ['COMPLETED', 'FAILED', 'PARTIAL'].includes(
    effectiveStatus,
  )


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
                {effectiveStatus}
              </p>

              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {completedFiles} completed ·{' '}
                {failedFiles} failed ·{' '}
                {processingFiles} processing ·{' '}
                {queuedFiles} waiting
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
                    {/* {file.status} */}
                    {String(file.status || '').toUpperCase()}
                  </p>
                </div>

                <Button
                  type="button"
                  intent="secondary"
                  // 
                  disabled={
                    !['COMPLETED', 'FAILED'].includes(
                      String(file.status || '').toUpperCase(),
                    ) ||
                    (!file.document_id && !file.data && !file.upload_id)
                  }
                  onClick={() => {
                    if (file.document_id) {
                      navigate(
                        `/app/ocr-test/history/${file.document_id}`,
                      )
                      return
                    }

                    if (file.data || file.upload_id) {
                      sessionStorage.setItem(
                        'ocr_test_result',
                        JSON.stringify({
                          // status: 
                          status: String(file.status || 'COMPLETED').toUpperCase(),
                          batch_id: batch.batch_id,
                          files: [file],
                        }),
                      )
                      navigate('/app/ocr-test/result')
                    }
                  }}
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