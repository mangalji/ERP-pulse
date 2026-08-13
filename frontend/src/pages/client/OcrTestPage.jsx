import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
]

const MAX_FILE_SIZE = 10 * 1024 * 1024

export default function OcrTestPage() {
  const navigate = useNavigate()
  const [selectedFile, setSelectedFile] = useState(null)
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')

  const loadHistory = useCallback(async () => {
    try {
      setHistoryLoading(true)
      setHistoryError('')

      const response = await apiClient.get('/ocr/history/')
      const data = response?.data?.data ?? response?.data ?? {}
      const results = Array.isArray(data)
        ? data
        : data?.results ?? data?.items ?? []

      setHistory(Array.isArray(results) ? results : [])
    } catch (err) {
      console.error('Failed to load OCR history:', err)
      setHistoryError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to load OCR history.',
      )
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const handleFileChange = (event) => {
    const file = event.target.files?.[0]

    setError('')
    setSelectedFile(null)

    if (!file) return

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Please select a PDF, PNG, JPG, JPEG or WEBP file.')
      event.target.value = ''
      return
    }

    if (file.size <= 0) {
      setError('The selected file is empty.')
      event.target.value = ''
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      setError('File size cannot exceed 10 MB.')
      event.target.value = ''
      return
    }

    setSelectedFile(file)
  }

  const handleExtract = async () => {
    if (!selectedFile || processing) {
      if (!selectedFile) setError('Please select a PDF or image first.')
      return
    }

    try {
      setError('')
      setProcessing(true)

      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await apiClient.post(
        '/ocr/test-extract/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        },
      )

      const responseData = response?.data ?? {}
      const result = responseData?.data ?? responseData

      if (!result || typeof result !== 'object') {
        throw new Error('OCR returned an invalid JSON response.')
      }

      sessionStorage.setItem(
        'ocr_test_result',
        JSON.stringify({
          status: responseData.status || 'COMPLETED',
          upload_id: responseData.upload_id || null,
          filename: responseData.filename || selectedFile.name,
          data: result,
        }),
      )

      navigate('/app/ocr-test/result')
    } catch (err) {
      console.error('OCR test failed:', err)

      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'OCR extraction failed.'

      setError(detail)
    } finally {
      setProcessing(false)
    }
  }

  const formatDate = (value) => {
    if (!value) return '--'

    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '--'

    return date.toLocaleString()
  }

  const statusLabel = (status) => {
    if (!status) return 'Unknown'
    return String(status).replaceAll('_', ' ')
  }

  return (
    <ClientLayout title="OCR Test" breadcrumb="OCR Test">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <Card className="p-6">
          <div className="mb-6">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
              OCR Test
            </h1>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Upload a PDF or image and extract structured data using the approved document extraction pipeline.
            </p>
          </div>

          <div className="rounded-lg border border-dashed border-[var(--color-border)] p-6">
            <label className="block text-sm font-medium text-[var(--color-ink)]">
              Upload PDF / Image
            </label>

            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
              onChange={handleFileChange}
              disabled={processing}
              className="mt-3 block w-full text-sm text-[var(--color-muted)]"
            />

            {error && (
              <p className="mt-3 text-sm text-[var(--color-negative)]">
                {error}
              </p>
            )}

            {selectedFile && (
              <div className="mt-4 rounded-md bg-[var(--color-canvas)] p-4">
                <p className="text-xs text-[var(--color-muted)]">
                  Selected file
                </p>

                <p className="mt-1 break-all text-sm font-medium text-[var(--color-ink)]">
                  {selectedFile.name}
                </p>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            )}

            <div className="mt-5 flex justify-end">
              <Button
                type="button"
                onClick={handleExtract}
                disabled={processing}
              >
                {processing ? 'Extracting...' : 'Extract Data'}
              </Button>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Recent OCR History
              </h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Previously processed files saved to your OCR history.
              </p>
            </div>

            <Button
              type="button"
              intent="secondary"
              onClick={loadHistory}
              disabled={historyLoading}
            >
              {historyLoading ? 'Refreshing...' : 'Refresh'}
            </Button>
          </div>

          {historyError && (
            <p className="mb-4 text-sm text-[var(--color-negative)]">
              {historyError}
            </p>
          )}

          {historyLoading ? (
            <div className="rounded-lg border border-[var(--color-border)] p-5 text-sm text-[var(--color-muted)]">
              Loading OCR history...
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                No OCR history yet
              </p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Your processed PDF and image files will appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)]">
              {history.map((item) => (
                <button
                  key={item.upload_id}
                  type="button"
                  onClick={() =>
                    item.document_id &&
                    navigate(`/app/ocr-test/history/${item.document_id}`)
                  }
                  disabled={!item.document_id}
                  className="flex w-full items-center justify-between gap-4 p-4 text-left transition hover:bg-[var(--color-canvas)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <div className="min-w-0">
                    <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                      {item.filename || 'Unnamed file'}
                    </p>

                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                      {formatDate(item.created_at)}
                    </p>
                  </div>

                  <div className="shrink-0 text-right">
                    <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                      {statusLabel(item.status)}
                    </p>

                    {item.document_type && (
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {statusLabel(item.document_type)}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
