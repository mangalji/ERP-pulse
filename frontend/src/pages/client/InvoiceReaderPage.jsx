import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { clientApi } from '../../services/client.js'

const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg']
const MAX_SIZE_MB = 10

const STATUS_TONE = {
  UPLOADED: 'neutral',
  PROCESSING: 'primary',
  EXTRACTED: 'primary',
  REVIEW_REQUIRED: 'netsuite',
  APPROVED: 'positive',
  REJECTED: 'negative',
  READY_FOR_NETSUITE: 'positive',
  FAILED: 'negative',
}

const STATUS_LABEL = {
  UPLOADED: 'Uploaded',
  PROCESSING: 'Processing',
  EXTRACTED: 'Extracted',
  REVIEW_REQUIRED: 'Review Required',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  READY_FOR_NETSUITE: 'Ready for NetSuite',
  FAILED: 'Failed',
}

export default function InvoiceReaderPage() {
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()
  const [batch, setBatch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const loadBatches = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.listInvoiceBatches({ limit: 20 })
      const list = data?.results ?? data ?? []
      setBatch(list[0] || null)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load invoice batches')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBatches()
  }, [loadBatches])

  const handleUpload = async (files) => {
    setError(null)
    setUploading(true)
    try {
      const data = await clientApi.uploadInvoices(files)
      setBatch(data)
      addToast('Invoices uploaded successfully', 'success')
    } catch (err) {
      setError(err.payload?.message || err.message || 'Upload failed')
      addToast(err.payload?.message || err.message || 'Upload failed', 'error')
    } finally {
      setUploading(false)
    }
  }

  const files = (batch?.files || []).filter((file) => {
    if (searchTerm && !file.original_filename.toLowerCase().includes(searchTerm.toLowerCase())) return false
    if (statusFilter !== 'all' && file.status !== statusFilter) return false
    return true
  })

  const handleApprove = async (fileId) => {
    try {
      await clientApi.reviewInvoiceFile(fileId, { action: 'approve' })
      const data = await clientApi.getInvoiceBatch(batch.id)
      setBatch(data)
      addToast('Invoice approved', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Approve failed', 'error')
    }
  }

  const handleReject = async (fileId) => {
    try {
      await clientApi.reviewInvoiceFile(fileId, { action: 'reject' })
      const data = await clientApi.getInvoiceBatch(batch.id)
      setBatch(data)
      addToast('Invoice rejected', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Reject failed', 'error')
    }
  }

  const handleRetry = async (fileId) => {
    try {
      await clientApi.retryInvoiceFile(fileId)
      const data = await clientApi.getInvoiceBatch(batch.id)
      setBatch(data)
      addToast('Retry triggered', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Retry failed', 'error')
    }
  }

  const handleDelete = async (fileId) => {
    try {
      await clientApi.deleteInvoiceFile(fileId)
      setBatch((b) => ({ ...b, files: (b.files || []).filter((f) => String(f.id) !== String(fileId)) }))
      addToast('File deleted', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Delete failed', 'error')
    }
  }

  return (
    <ClientLayout title="Invoice Reader" breadcrumb="Invoice Reader">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Invoice Reader
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            Upload invoices in PDF, PNG, JPG, or JPEG. OCR and AI extract data automatically for your review.
          </p>
        </div>

        {/* Upload */}
        <Card className="p-6">
          <label
            htmlFor="client-invoice-upload"
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-[var(--color-border)] px-6 py-10 text-center transition-colors hover:border-[var(--color-primary)]"
          >
            <input
              id="client-invoice-upload"
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
              disabled={uploading}
              onChange={(e) => handleUpload(Array.from(e.target.files))}
            />
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                <path d="M12 16V4M7 9l5-5 5 5" />
                <path d="M4 20h16" />
              </svg>
            </span>
            <span className="text-sm font-medium text-[var(--color-ink)]">
              {uploading ? 'Uploading...' : 'Drag & drop files here, or click to browse'}
            </span>
            <span className="text-xs text-[var(--color-muted)]">
              Supports PDF, PNG, JPG, JPEG · max {MAX_SIZE_MB}MB each
            </span>
          </label>
          {error && <p className="mt-3 text-sm text-[var(--color-negative)]">{error}</p>}
        </Card>

        {/* Current batch */}
        <Card className="p-6">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                {batch ? `Batch #${batch.id}` : 'Invoice Batches'}
              </h2>
              {batch && (
                <div className="mt-1 flex items-center gap-2 text-xs text-[var(--color-muted)]">
                  <span>{batch.total_files || 0} files</span>
                  <span>·</span>
                  <span>{batch.processed_files || 0} processed</span>
                  <span>·</span>
                  <span>{batch.failed_files || 0} failed</span>
                  <Badge tone={STATUS_TONE[batch.status] || 'neutral'}>{batch.status}</Badge>
                </div>
              )}
            </div>
            {batch && (
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  type="text"
                  placeholder="Search files..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="all">All statuses</option>
                  {Object.keys(STATUS_LABEL).map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !batch ? (
            <EmptyState
              title="No batches yet"
              description="Upload invoices above to start the OCR and AI extraction pipeline."
            />
          ) : files.length === 0 ? (
            <EmptyState title="No files match your filters" description="Try adjusting the search or status filter." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                    <th className="pb-2 pr-4 font-medium">Filename</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Confidence</th>
                    <th className="pb-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => {
                    const extraction = file.extraction
                    const confidence = extraction?.confidence_score
                    return (
                      <tr key={file.id} className="border-b border-[var(--color-border)] last:border-0">
                        <td className="py-3 pr-4 font-medium text-[var(--color-ink)]">{file.original_filename}</td>
                        <td className="py-3 pr-4">
                          <Badge tone={STATUS_TONE[file.status] || 'neutral'}>
                            {STATUS_LABEL[file.status] || file.status}
                          </Badge>
                        </td>
                        <td className="py-3 pr-4 font-mono-tabular text-[var(--color-ink-soft)]">
                          {confidence != null ? `${Math.round(confidence * 100)}%` : '—'}
                        </td>
                        <td className="py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button size="sm" intent="ghost" onClick={() => navigate(`/app/invoice-reader/${file.id}`)}>
                              View Detail
                            </Button>
                            {extraction && (
                              <>
                                <Button size="sm" intent="secondary" onClick={() => handleApprove(file.id)}>
                                  Approve
                                </Button>
                                <Button size="sm" intent="secondary" onClick={() => handleReject(file.id)}>
                                  Reject
                                </Button>
                              </>
                            )}
                            <Button size="sm" intent="ghost" onClick={() => handleRetry(file.id)}>
                              Retry
                            </Button>
                            <Button size="sm" intent="ghost" onClick={() => handleDelete(file.id)}>
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </ClientLayout>
  )
}
