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
  const [reviewHistory, setReviewHistory] = useState([])
  [selectedFileId, setSelectedFileId] = useState(null)
  [validationErrors, setValidationErrors] = useState({})
  [showJsonDrawer, setShowJsonDrawer] = useState(false)
  [showHistoryDrawer, setShowHistoryDrawer] = useState(false)
  [searchTerm, setSearchTerm] = useState('')
  [statusFilter, setStatusFilter] = useState('all')
  [sortBy, setSortBy] = useState('created_at')
  [sortOrder, setSortOrder] = useState('desc')
  [selectedFiles, setSelectedFiles] = useState(new Set())

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

  const handleViewJson = (file) => {
    setSelectedFileId(file.id)
    setShowJsonDrawer(true)
  }

  const handleViewHistory = (file) => {
    setSelectedFileId(file.id)
    // Fetch history for this file
    invoiceApi.getFileHistory(file.id).then(history => {
      setReviewHistory(history)
    }).catch(err => {
      console.error('Failed to fetch history:', err)
      setReviewHistory([])
    })
    setShowHistoryDrawer(true)
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
      setEditForm({})
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Save failed')
    }
  }

  const handleApprove = async (fileId) => {
    try {
      await invoiceApi.reviewFile(fileId, { action: 'approve' })
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Approve failed')
    }
  }

  const handleReject = async (fileId) => {
    try {
      await invoiceApi.reviewFile(fileId, { action: 'reject' })
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Reject failed')
    }
  }

  const handlePrepareForNetSuite = async (fileId) => {
    try {
      await invoiceApi.prepareForNetSuite(fileId)
      const data = await invoiceApi.getBatch(batch.id)
      setBatch(data)
    } catch (err) {
      setError(err.message || 'Prepare for NetSuite failed')
    }
  }

  const handleToggleSelectAll = () => {
    if (!batch || !batch.files) return
    const allSelected = selectedFiles.size === batch.files.length
    if (allSelected) {
      setSelectedFiles(new Set())
    } else {
      const newSet = new Set()
      batch.files.forEach(file => newSet.add(file.id))
      setSelectedFiles(newSet)
    }
  }

  const handleToggleSelect = (fileId) => {
    const newSet = new Set(selectedFiles)
    if (newSet.has(fileId)) {
      newSet.delete(fileId)
    } else {
      newSet.add(fileId)
    }
    setSelectedFiles(newSet)
  }

  const getFilteredAndSortedFiles = () => {
    if (!batch || !batch.files) return []
    let filtered = batch.files.filter(file => {
      // Search filter
      if (searchTerm && !file.original_filename.toLowerCase().includes(searchTerm.toLowerCase())) {
        return false
      }
      // Status filter
      if (statusFilter !== 'all' && file.status !== statusFilter) {
        return false
      }
      return true
    })

    // Sort
    filtered.sort((a, b) => {
      let comparison = 0
      if (sortBy === 'created_at') {
        comparison = new Date(a.created_at) - new Date(b.created_at)
      } else if (sortBy === 'filename') {
        comparison = a.original_filename.localeCompare(b.original_filename)
      } else if (sortBy === 'status') {
        comparison = a.status.localeCompare(b.status)
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return filtered
  }

  const getStatusLabel = (status) => {
    const labels = {
      UPLOADING: 'Uploading',
      PROCESSING: 'Processing',
      EXTRACTED: 'Extracted',
      REVIEW_REQUIRED: 'Review Required',
      APPROVED: 'Approved',
      REJECTED: 'Rejected',
      READY_FOR_NETSUITE: 'Ready for NetSuite',
      FAILED: 'Failed',
    }
    return labels[status] || status
  }

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'UPLOADING': return 'bg-blue-100 text-blue-800'
      case 'PROCESSING': return 'bg-yellow-100 text-yellow-800'
      case 'EXTRACTED': return 'bg-indigo-100 text-indigo-800'
      case 'REVIEW_REQUIRED': return 'bg-purple-100 text-purple-800'
      case 'APPROVED': return 'bg-green-100 text-green-800'
      case 'REJECTED': return 'bg-red-100 text-red-800'
      case 'READY_FOR_NETSUITE': return 'bg-blue-100 text-blue-800'
      case 'FAILED': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
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

        {/* Section 3: Controls */}
        {batch && (
          <div className="flex flex-wrap items-center gap-4 mb-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={selectedFiles.size === (batch.files?.length || 0)}
                onChange={handleToggleSelectAll}
                className="h-4 w-4 text-blue-600"
              />
              <span className="text-sm font-medium">Select All</span>
            </div>
            <div className="relative">
              <input
                type="text"
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-64 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Statuses</option>
                <option value="UPLOADED">Uploaded</option>
                <option value="PROCESSING">Processing</option>
                <option value="EXTRACTED">Extracted</option>
                <option value="REVIEW_REQUIRED">Review Required</option>
                <option value="APPROVED">Approved</option>
                <option value="REJECTED">Rejected</option>
                <option value="READY_FOR_NETSUITE">Ready for NetSuite</option>
                <option value="FAILED">Failed</option>
              </select>
            </div>
            <div className="flex space-x-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="created_at">Date</option>
                <option value="filename">Filename</option>
                <option value="status">Status</option>
              </select>
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
          </div>
        )}

        {/* Section 4: Batch Status & Files */}
        {batch && (
          <div className="bg-white shadow rounded-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Batch #{batch.id}</h2>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadgeClass(batch.status)}`}>
                {getStatusLabel(batch.status)}
              </span>
            </div>

            {/* Section 5: Extracted Data Table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Select</th>
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
                  {getFilteredAndSortedFiles().map((file) => {
                    const extraction = file.extraction
                    const data = extraction?.extracted_json || {}
                    const isEditing = editingId === file.id
                    const confidence = extraction?.confidence_score || 0
                    const isSelected = selectedFiles.has(file.id)

                    return (
                      <tr key={file.id} className={isSelected ? 'bg-blue-50' : ''}>
                        <td className="px-4 py-3 text-sm">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelect(file.id)}
                            className="h-4 w-4 text-blue-600"
                          />
                        </td>
                        <td className="px-4 py-3 text-sm">{file.original_filename}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadgeClass(file.status)}`}>
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
                                    onClick={() => handleViewJson(file)}
                                    className="text-green-600 hover:text-green-800"
                                  >
                                    JSON
                                  </button>
                                  <button
                                    onClick={() => handleViewHistory(file)}
                                    className="text-blue-600 hover:text-blue-800"
                                  >
                                    History
                                  </button>
                                  <button
                                    onClick={() => startEdit(file)}
                                    className="text-blue-600 hover:text-blue-800"
                                  >
                                    Edit
                                  </button>
                                </>
                              )}
                              {file.status === 'EXTRACTED' && (
                                <>
                                  <button
                                    onClick={() => handleApprove(file.id)}
                                    className="text-green-600 hover:text-green-800"
                                  >
                                    Approve
                                  </button>
                                  <button
                                    onClick={() => handleReject(file.id)}
                                    className="text-red-600 hover:text-red-800"
                                  >
                                    Reject
                                  </button>
                                  <button
                                    onClick={() => handlePrepareForNetSuite(file.id)}
                                    className="text-yellow-600 hover:text-yellow-800"
                                  >
                                    Prepare for NetSuite
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

      {/* JSON Drawer */}
      {showJsonDrawer && selectedFileId && (
        <div className="fixed inset-0 z-50 flex items-end bg-black bg-opacity-50">
          <div className="w-full max-w-md bg-white p-6 rounded-t-lg shadow-lg">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold">Extracted JSON</h3>
              <button
                onClick={() => setShowJsonDrawer(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ×
              </button>
            </div>
            <div className="h-96 overflow-auto bg-gray-50 p-4 rounded">
              <pre className="text-xs">{JSON.stringify(
                batch?.files.find(f => f.id === selectedFileId)?.extraction?.extracted_json || {},
                null,
                2
              )}</pre>
            </div>
          </div>
        </div>
      )}

      {/* History Drawer */}
      {showHistoryDrawer && selectedFileId && (
        <div className="fixed inset-0 z-50 flex items-end bg-black bg-opacity-50">
          <div className="w-full max-w-md bg-white p-6 rounded-t-lg shadow-lg">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold">Review History</h3>
              <button
                onClick={() => setShowHistoryDrawer(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ×
              </button>
            </div>
            <div className="h-96 overflow-auto">
              {reviewHistory.length > 0 ? (
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
                    {reviewHistory.map((record) => (
                      <tr key={record.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm">{record.field}</td>
                        <td className="px-4 py-3 text-sm">{record.old_value}</td>
                        <td className="px-4 py-3 text-sm">{record.new_value}</td>
                        <td className="px-4 py-3 text-sm">{record.edited_by?.get_full_name || 'Unknown'}</td>
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
    </DashboardLayout>
  )
}