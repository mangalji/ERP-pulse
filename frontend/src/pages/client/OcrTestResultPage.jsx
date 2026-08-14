import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'

export default function OcrTestResultPage() {
  const navigate = useNavigate()
  const { documentId } = useParams()

  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadResult = async () => {
      if (!documentId) {
        const result = sessionStorage.getItem('ocr_test_result')

        if (!result) {
          navigate('/app/ocr-test', { replace: true })
          return
        }

        setText(result)
        return
      }

      try {
        setLoading(true)
        setError('')

        const response = await apiClient.get(
          `/ocr/documents/${documentId}/history/`,
        )

        const payload = response?.data?.data ?? response?.data ?? {}
        const versions = payload?.versions ?? []

        if (!versions.length) {
          throw new Error('No saved OCR version was found.')
        }

        const latest = [...versions].sort(
          (a, b) =>
            (b.version_number ?? 0) - (a.version_number ?? 0),
        )[0]

        const savedResult = {
          status:
            latest?.normalized_json?.status ||
            (payload.status === 'EXTRACTED'
              ? 'COMPLETED'
              : payload.status || 'COMPLETED'),
          upload_id: payload.upload_id || null,
          filename: payload.filename || null,
          data: latest.normalized_json ?? {},
        }

        setText(JSON.stringify(savedResult, null, 2))
      } catch (err) {
        console.error('Failed to load saved OCR result:', err)

        setError(
          err?.response?.data?.detail ||
            err?.response?.data?.error ||
            err?.message ||
            'Failed to load saved OCR result.',
        )
      } finally {
        setLoading(false)
      }
    }

    loadResult()
  }, [documentId, navigate])

  return (
    <ClientLayout title="OCR Result" breadcrumb="OCR Result">
      <div className="mx-auto w-full max-w-5xl">
        <Card className="p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                OCR Result
              </h1>

              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Saved OCR result.
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

          {loading ? (
            <div className="rounded-lg border border-[var(--color-border)] p-6 text-sm text-[var(--color-muted)]">
              Loading saved OCR result...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
              {error}
            </div>
          ) : (
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-5">
              <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-[var(--color-ink)]">
                {text}
              </pre>
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
