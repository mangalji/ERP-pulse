import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import OcrReviewWorkspace from '../../components/ocr/OcrReviewWorkspace.jsx'

function isPdf(filename) {
  return /\.pdf$/i.test(filename || '')
}

export default function OcrTestResultPage() {
  const navigate = useNavigate()
  const { documentId } = useParams()

  // const [text, setText] = useState('')
  // const [loading, setLoading] = useState(false)
  // const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [remotePreviewUrl, setRemotePreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')

  useEffect(() => {
    const loadResult = async () => {
      if (!documentId) {
        const result = sessionStorage.getItem('ocr_test_result')

        // if (!result) {
        if (!saved) {
          navigate('/app/ocr-test', { replace: true })
          return
        }
        try {
          const parsed = JSON.parse(saved)
          const files = parsed?.files || []
          const firstResult = files.find((item) => item?.data) || files[0] || null
          setResult(firstResult)
        } catch (err) {
          console.error('Failed to load live OCR result:', err)
          setError('Failed to load OCR result from the current session.')
        }

        // setText(result)
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

        const reviewedData = latest?.reviewed_json && typeof latest.reviewed_json === 'object' && Object.keys(latest.reviewed_json).length ? latest.reviewed_json : latest?.normalized_json ?? {}

        // const savedResult = {
        //   status:
        //     latest?.normalized_json?.status ||
        //     (payload.status === 'EXTRACTED'
        //       ? 'COMPLETED'
        //       : payload.status || 'COMPLETED'),
        //   upload_id: payload.upload_id || null,
        //   filename: payload.filename || null,
        //   data: latest.normalized_json ?? {},
        // }

        setResult({
          status: payload.status || 'APPROVED',
          upload_id: payload.upload_id || null,
          document_id: payload.id || documentId,
          version_id: latest.id || null,
          version_number: latest.version_number || null,
          filename: payload.filename || 'OCR document',
          preview_url: payload.upload_id
            ? `/ocr/test-extract/uploads/${payload.upload_id}/preview/`
            : null,
          data: reviewedData,
        })

        // setText(JSON.stringify(savedResult, null, 2))
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

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    const loadRemotePreview = async () => {
      setPreviewError('')
      setRemotePreviewUrl(null)

      if (!result?.preview_url) return

      try {
        const response = await apiClient.get(
          result.preview_url,
          { responseType: 'blob' },
        )

        if (cancelled) return

        objectUrl = URL.createObjectURL(response.data)
        setRemotePreviewUrl(objectUrl)
      } catch (err) {
        console.error('Failed to load OCR history preview:', err)

        if (!cancelled) {
          setPreviewError(
            err?.response?.data?.detail ||
              err?.message ||
              'Unable to load file preview.',
          )
        }
      }
    }

    loadRemotePreview()

    return () => {
      cancelled = true

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [result?.preview_url])

  const handleSaved = (savedResult) => {
    setResult((current) => ({
      ...current,
      ...savedResult,
    }))
  }

  const previewIsPdf = isPdf(result?.filename)


//   return (
//     <ClientLayout title="OCR Result" breadcrumb="OCR Result">
//       <div className="mx-auto w-full max-w-7xl space-y-6">
//         <Card className="p-6">
//           <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
//             <div>
//               <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
//                 OCR Result
//               </h1>

//               <p className="mt-1 text-sm text-[var(--color-muted)]">
//                 Saved OCR result.
//               </p>
//             </div>

//             <Button
//               type="button"
//               intent="secondary"
//               onClick={() => navigate('/app/ocr-test')}
//             >
//               Back to OCR
//             </Button>
//           </div>

//           {loading ? (
//             <div className="rounded-lg border border-[var(--color-border)] p-6 text-sm text-[var(--color-muted)]">
//               Loading saved OCR result...
//             </div>
//           ) : error ? (
//             <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
//               {error}
//             </div>
//           ) : (
//             <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-5">
//               <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-[var(--color-ink)]">
//                 {text}
//               </pre>
//             </div>
//           )}
//         </Card>
//       </div>
//     </ClientLayout>
//   )
// }
  return (
    <ClientLayout title="OCR Result" breadcrumb="OCR Result">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
              OCR Review
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Review, edit and save the extracted document data.
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
          <Card className="p-6 text-sm text-[var(--color-muted)]">
            Loading saved OCR result...
          </Card>
        ) : error ? (
          <Card className="p-6">
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700">
              {error}
            </div>
          </Card>
        ) : result ? (
          <div className="grid min-h-[600px] gap-6 lg:grid-cols-2">
            <Card className="flex min-h-[560px] flex-col overflow-hidden">
              <div className="border-b border-[var(--color-border)] p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                  File Preview
                </p>
                <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                  {result.filename || 'OCR document'}
                </p>
              </div>

              <div className="flex min-h-0 flex-1 items-center justify-center bg-[var(--color-canvas)] p-4">
                {previewError ? (
                  <div className="max-w-md rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
                    {previewError}
                  </div>
                ) : result.preview_url && remotePreviewUrl ? (
                  previewIsPdf ? (
                    <iframe
                      title={result.filename || 'OCR document'}
                      src={remotePreviewUrl}
                      className="min-h-[480px] w-full rounded-lg border border-[var(--color-border)] bg-white"
                    />
                  ) : (
                    <img
                      src={remotePreviewUrl}
                      alt={result.filename || 'OCR document'}
                      className="max-h-[480px] max-w-full rounded-lg object-contain shadow-sm"
                    />
                  )
                ) : (
                  <p className="text-sm text-[var(--color-muted)]">
                    File preview is not available for this record.
                  </p>
                )}
              </div>
            </Card>

            <Card className="flex min-h-[560px] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    OCR Review
                  </p>
                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {result.filename || 'OCR document'}
                  </p>
                </div>

                <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  {String(result.status || 'APPROVED').replaceAll('_', ' ')}
                </span>
              </div>

              <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-surface)] p-4">
                <OcrReviewWorkspace
                  result={result}
                  onSaved={handleSaved}
                />
              </div>
            </Card>
          </div>
        ) : (
          <Card className="p-6 text-sm text-[var(--color-muted)]">
            No OCR result found.
          </Card>
        )}
      </div>
    </ClientLayout>
  )
}
