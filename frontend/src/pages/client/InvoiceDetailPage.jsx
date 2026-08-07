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

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const { toasts, addToast, removeToast } = useToast()
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [payload, setPayload] = useState(null)
  const [showPayload, setShowPayload] = useState(false)

  useEffect(() => {
    loadFile()
  }, [id])

  const loadFile = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await invoiceApi.getFile(id)
      setFile(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load invoice')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    try {
      await invoiceApi.reviewFile(id, { action: 'approve' })
      await loadFile()
      addToast('Invoice approved', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Approve failed', 'error')
    }
  }

  const handleReject = async () => {
    try {
      await invoiceApi.reviewFile(id, { action: 'reject' })
      await loadFile()
      addToast('Invoice rejected', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Reject failed', 'error')
    }
  }

  const handleSaveEdit = async () => {
    try {
      const result = await invoiceApi.patchExtraction(id, editForm)
      setFile(result)
      setEditing(false)
      addToast('Changes saved', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Save failed', 'error')
    }
  }

  const handleViewHistory = () => {
    const history = file?.extraction?.review_history || []
    setHistory(history)
    setShowHistory(true)
  }

  const handlePreviewPayload = async () => {
    try {
      const data = await invoiceApi.previewPayload(id)
      setPayload(data.payload)
      setShowPayload(true)
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to generate preview', 'error')
    }
  }

  const extraction = file?.extraction
  const data = extraction?.extracted_json || {}
  const confidence = extraction?.confidence_score || 0
  const validationErrors = extraction?.validation_errors || []

  if (loading) {
    return (
      <ClientLayout title="Invoice Detail" breadcrumb="Invoice Detail">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

  if (error || !file) {
    return (
      <ClientLayout title="Invoice Detail" breadcrumb="Invoice Detail">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error || 'Invoice not found'}</p>
          <Button intent="secondary" onClick={loadFile} className="mt-4">Try again</Button>
        </Card>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout title="Invoice Detail" breadcrumb="Invoice Detail">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            {file.original_filename}
          </h1>
          <div className="flex items-center gap-2">
            <Badge tone={STATUS_TONE[file.status] || 'neutral'}>{STATUS_LABEL[file.status] || file.status}</Badge>
            {confidence != null && (
              <span className={`text-xs font-medium ${confidence >= 0.7 ? 'text-[var(--color-positive)]' : 'text-[var(--color-negative)]'}`}>
                {Math.round(confidence * 100)}% confidence
              </span>
            )}
          </div>
        </div>

        {validationErrors.length > 0 && (
          <Card className="p-5 border-l-4 border-[var(--color-negative)]">
            <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-negative)]">Validation Errors</h3>
            <ul className="mt-2 flex flex-col gap-1">
              {validationErrors.map((err, idx) => (
                <li key={idx} className="text-sm text-[var(--color-ink-soft)]">• {err.message}</li>
              ))}
            </ul>
          </Card>
        )}

        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Extracted Data</h3>
            <div className="flex gap-2">
              <Button intent="secondary" size="sm" onClick={handleViewHistory}>History</Button>
              <Button intent="secondary" size="sm" onClick={handlePreviewPayload}>Payload Preview</Button>
              {extraction && file.status === 'EXTRACTED' && (
                <>
                  <Button intent="secondary" size="sm" onClick={() => { setEditForm({ ...data }); setEditing(true) }}>Edit</Button>
                  <Button size="sm" onClick={handleApprove}>Approve</Button>
                  <Button intent="negative" size="sm" onClick={handleReject}>Reject</Button>
                </>
              )}
            </div>
          </div>

          {editing ? (
            <div className="flex flex-col gap-4">
              {Object.keys(data).map((key) => (
                <div key={key} className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-[var(--color-ink-soft)] capitalize">{key}</label>
                  <input
                    type="text"
                    value={editForm[key] ?? data[key] ?? ''}
                    onChange={(e) => setEditForm({ ...editForm, [key]: e.target.value })}
                    className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <Button onClick={handleSaveEdit}>Save</Button>
                <Button intent="secondary" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <dl className="flex flex-col gap-3">
              {Object.entries(data).map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)] capitalize">{key}</dt>
                  <dd className="text-sm text-[var(--color-ink)]">{value ?? '—'}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>

        <Toast toasts={toasts} removeToast={removeToast} />

        {/* History Drawer */}
        {showHistory && (
          <div className="fixed inset-0 z-50 flex items-end bg-black bg-opacity-50">
            <div className="w-full max-w-md bg-white p-6 rounded-t-lg shadow-lg">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-bold">Review History</h3>
                <button onClick={() => setShowHistory(false)} className="text-gray-500 hover:text-gray-700">×</button>
              </div>
              <div className="h-96 overflow-auto">
                {history.length > 0 ? (
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Field</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Old Value</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">New Value</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Edited By</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Edited At</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {history.map((record) => (
                        <tr key={record.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm">{record.field}</td>
                          <td className="px-4 py-3 text-sm">{record.old_value}</td>
                          <td className="px-4 py-3 text-sm">{record.new_value}</td>
                          <td className="px-4 py-3 text-sm">{record.edited_by_name || record.edited_by?.get_full_name || 'Unknown'}</td>
                          <td className="px-4 py-3 text-sm">{new Date(record.edited_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-gray-500 text-center py-8">No history available.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Payload Preview Drawer */}
        {showPayload && (
          <div className="fixed inset-0 z-50 flex items-end bg-black bg-opacity-50">
            <div className="w-full max-w-md bg-white p-6 rounded-t-lg shadow-lg">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-bold">NetSuite Payload Preview</h3>
                <button onClick={() => setShowPayload(false)} className="text-gray-500 hover:text-gray-700">×</button>
              </div>
              <div className="h-96 overflow-auto bg-gray-50 p-4 rounded">
                <pre className="text-xs">{JSON.stringify(payload, null, 2)}</pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </ClientLayout>
  )
}
