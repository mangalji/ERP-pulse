import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { invoiceApi } from '../../services/invoice.js'

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

export default function PayloadPreviewPage() {
  const { id } = useParams()
  const { toasts, addToast, removeToast } = useToast()
  const [file, setFile] = useState(null)
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [fileData, payloadData] = await Promise.all([
        invoiceApi.getFile(id),
        invoiceApi.previewPayload(id),
      ])
      setFile(fileData)
      setPayload(payloadData.payload)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load payload preview')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <ClientLayout title="Payload Preview" breadcrumb="Payload Preview">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

  if (error || !file) {
    return (
      <ClientLayout title="Payload Preview" breadcrumb="Payload Preview">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error || 'Invoice not found'}</p>
          <Button intent="secondary" onClick={loadData} className="mt-4">Try again</Button>
        </Card>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout title="Payload Preview" breadcrumb="Payload Preview">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            NetSuite Payload Preview
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            {file.original_filename} · <Badge tone={STATUS_TONE[file.status] || 'neutral'}>{STATUS_LABEL[file.status] || file.status}</Badge>
          </p>
        </div>

        <Card className="p-5">
          <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Payload</h3>
          <div className="h-[60vh] overflow-auto rounded-lg bg-gray-50 p-4">
            <pre className="text-xs">{JSON.stringify(payload || {}, null, 2)}</pre>
          </div>
        </Card>

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </ClientLayout>
  )
}
