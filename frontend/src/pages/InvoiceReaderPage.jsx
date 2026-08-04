import { useState, useCallback, useEffect } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import { invoiceApi } from '../services/invoice.js'

const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg']
const MAX_FILES = 1000
const MAX_SIZE_MB = 10

function ConfidenceBadge({ score }) {
  let color = 'bg-red-100 text-red-800'
  if (score >= 0.9) color = 'bg-green-100 text-green-800'
  else if (score >= 0.7) color = 'bg-yellow-100 text-yellow-800'
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${color}`}>
      {Math.round((score || 0) * 100)}%
    </span>
  )
}

export default function InvoiceReaderPage() {
  const [batch, setBatch] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})

  const handleUpload = useCallback(async (files) => {
    setError(null)
    setUploading(true)
    try {
      const data = await invoiceApi.upload(files)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [])

  // Polling for batch status
  useEffect(() => {
    if (!batch || !batch.id) return
    
    const isTerminal = batch.status === 'COMPLETED' || batch.status === 'FAILED'
    if (isTerminal) return

    const interval = setInterval(async () => {
      try {
        const data = await invoiceApi.getBatch(batch.id)
        setBatch(data)
      } catch (err) {
        console.error('Polling failed:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [batch])

  const handleRetry = async (fileId) => {
    try {
      await invoiceApi.retryFile(fileId)
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Retry failed')
    }
  }

  const handleDelete = async (fileId) => {
    try {
      await invoiceApi.deleteFile(fileId)
      setBatch((b) => ({
        ...b,
        files: b.files.filter((f) => f.id !== fileId),
      }))
    } catch (err) {
      setError(err.message || 'Delete failed')
    }
  }

  const handleDownloadJson = (file) => {
    const extraction = file.extraction
    if (!extraction) return
    const blob = new Blob([JSON.stringify(extraction.extracted_json, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${file.original_filename}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const startEdit = (file) => {
    const data = file.extraction?.extracted_json || {}
    setEditingId(file.id)
    setEditForm({
      vendor: data.vendor || '',
      invoice_number: data.invoice_number || '',
      invoice_date: data.invoice_date || '',
      currency: data.currency || '',
      total_amount: data.total_amount || '',
      tax_amount: data.tax_amount || '',
      gst: data.gst || '',
      remarks: data.remarks || '',
    })
  }

  const saveEdit = async (fileId) => {
    try {
      await invoiceApi.patchExtraction(fileId, editForm)
      setEditingId(null)
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Save failed')
    }
  }

  const getStatusLabel = (status) => {
    const labels = {
      UPLOADING: 'Uploading',
      PROCESSING: 'Processing',
      COMPLETED: 'Completed',
      FAILED: 'Failed',
    }
    return labels[status] || status
  }

  return (
    <DashboardLayout title="Invoice Reader">
      <div className="space-y-6">
        {/* Section 1: Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoice Reader</h1>
          <p className="text-gray-600">
            Upload invoices in PDF, PNG, JPG, or JPEG format. Extract data using OCR and AI.
          </p>
        </div>

        {/* Section 2: Drag & Drop Upload */}
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(e) => handleUpload(Array.from(e.target.files))}
            disabled={uploading}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <div className="space-y-2">
              <p className="text-lg font-medium text-gray-700">
                {uploading ? 'Uploading...' : 'Drag & drop files here, or click to browse'}
              </p>
              <p className="text-sm text-gray-500">
                Supports PDF, PNG, JPG, JPEG (max {MAX_FILES} files, {MAX_SIZE_MB}MB each)
              </p>
            </div>
          </label>
        </div>

        {/* Section 3 & 4: Batch Status & Files */}
        {batch && (
          <div className="bg-white shadow rounded-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Batch #{batch.id}</h2>
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                {getStatusLabel(batch.status)}
              </span>
            </div>

            {/* Section 5: Extracted Data Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Vendor</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Invoice #</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Currency</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tax</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">GST</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Remarks</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {batch.files?.map((file) => {
                    const extraction = file.extraction
                    const data = extraction?.extracted_json || {}
                    const isEditing = editingId === file.id
                    const confidence = extraction?.confidence_score || 0

                    return (
                      <tr key={file.id}>
                        <td className="px-4 py-3 text-sm">{file.original_filename}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            file.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                            file.status === 'FAILED' ? 'bg-red-100 text-red-800' :
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {getStatusLabel(file.status)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {extraction ? <ConfidenceBadge score={confidence} /> : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.vendor}
                              onChange={(e) => setEditForm({ ...editForm, vendor: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.vendor || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.invoice_number}
                              onChange={(e) => setEditForm({ ...editForm, invoice_number: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.invoice_number || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.invoice_date}
                              onChange={(e) => setEditForm({ ...editForm, invoice_date: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.invoice_date || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.currency}
                              onChange={(e) => setEditForm({ ...editForm, currency: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.currency || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              type="number"
                              value={editForm.total_amount}
                              onChange={(e) => setEditForm({ ...editForm, total_amount: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.total_amount != null ? `$${Number(data.total_amount).toLocaleString()}` : '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              type="number"
                              value={editForm.tax_amount}
                              onChange={(e) => setEditForm({ ...editForm, tax_amount: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.tax_amount != null ? `$${Number(data.tax_amount).toLocaleString()}` : '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.gst}
                              onChange={(e) => setEditForm({ ...editForm, gst: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.gst || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {isEditing ? (
                            <input
                              value={editForm.remarks}
                              onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                              className="border rounded px-2 py-1 w-full"
                            />
                          ) : (
                            data.remarks || '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm space-x-2">
                          {isEditing ? (
                            <>
                              <button
                                onClick={() => saveEdit(file.id)}
                                className="text-green-600 hover:text-green-800"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingId(null)}
                                className="text-gray-600 hover:text-gray-800"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              {extraction && (
                                <>
                                  <button
                                    onClick={() => handleDownloadJson(file)}
                                    className="text-green-600 hover:text-green-800"
                                  >
                                    JSON
                                  </button>
                                  <button
                                    onClick={() => startEdit(file)}
                                    className="text-blue-600 hover:text-blue-800"
                                  >
                                    Edit
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => handleRetry(file.id)}
                                className="text-yellow-600 hover:text-yellow-800"
                              >
                                Retry
                              </button>
                              <button
                                onClick={() => handleDelete(file.id)}
                                className="text-red-600 hover:text-red-800"
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {batch.files?.length === 0 && (
              <p className="text-gray-500 text-center py-4">No files uploaded yet.</p>
            )}
          </div>
        )}

        {error && <div className="p-4 bg-red-50 text-red-700 rounded">{error}</div>}
      </div>
    </DashboardLayout>
  )
}