import { useEffect, useState } from 'react'
import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import OcrReviewWorkspace from './OcrReviewWorkspace.jsx'
import apiClient from '../../services/apiClient.js'

function isPdf(filename) {
  return /\.pdf$/i.test(filename || '')
}

export default function OcrValidationInlineEditor({
  result,
  customFieldTypes = {},
  connectionId = null,
  onSaved,
  onClose,
}) {
  const [remotePreviewUrl, setRemotePreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    const loadPreview = async () => {
      setPreviewError('')
      setRemotePreviewUrl(null)

      if (!result?.upload_id) {
        setPreviewError(
          'The original PDF preview is not available for this OCR result.',
        )
        return
      }

      try {
        const response = await apiClient.get(
          `/ocr/extract/uploads/${result.upload_id}/preview/`,
          { responseType: 'blob' },
        )

        if (cancelled) return

        objectUrl = URL.createObjectURL(response.data)
        setRemotePreviewUrl(objectUrl)
      } catch (err) {
        console.error('Failed to load inline OCR preview:', err)

        if (!cancelled) {
          setPreviewError(
            err?.response?.data?.detail ||
              err?.message ||
              'Unable to load the original document preview.',
          )
        }
      }
    }

    loadPreview()

    return () => {
      cancelled = true

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [result?.upload_id])

  if (!result) return null

  const previewAvailable = Boolean(remotePreviewUrl)
  const previewIsPdf = isPdf(result.filename)

  return (
    <Card className="overflow-hidden border border-blue-200 bg-blue-50/30 p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-200 bg-blue-50 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-blue-900">
            Edit OCR Data
          </p>
          <p className="mt-0.5 text-xs text-blue-700">
            Make the required correction below, save it, and then validate again.
          </p>
        </div>

        <Button
          type="button"
          intent="ghost"
          size="sm"
          onClick={onClose}
        >
          Close
        </Button>
      </div>

      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-white">
          <div className="border-b border-[var(--color-border)] px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
              Original Document
            </p>
            <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
              {result.filename || 'OCR document'}
            </p>
          </div>

          <div className="flex min-h-[520px] items-center justify-center bg-[var(--color-canvas)] p-3">
            {previewError ? (
              <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {previewError}
              </div>
            ) : previewAvailable && previewIsPdf ? (
              <iframe
                title={result.filename || 'OCR document'}
                src={remotePreviewUrl}
                className="h-[520px] w-full rounded-md border border-[var(--color-border)] bg-white"
              />
            ) : previewAvailable ? (
              <img
                src={remotePreviewUrl}
                alt={result.filename || 'OCR document'}
                className="max-h-[520px] max-w-full rounded-md object-contain"
              />
            ) : (
              <p className="text-sm text-[var(--color-muted)]">
                Loading document preview...
              </p>
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-[var(--color-border)] bg-white p-4">
          <OcrReviewWorkspace
            result={result}
            onSaved={onSaved}
            customFieldTypes={customFieldTypes}
            connectionId={connectionId}
            showPost={false}
            showFieldMapping={false}
            compact
          />
        </div>
      </div>
    </Card>
  )
}
