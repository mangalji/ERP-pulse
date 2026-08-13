import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'

export default function OcrTestResultPage() {
  const navigate = useNavigate()
  const [result, setResult] = useState(null)

  useEffect(() => {
    const storedResult = sessionStorage.getItem('ocr_test_result')

    if (!storedResult) {
      navigate('/app/ocr-test', { replace: true })
      return
    }

    try {
      const parsedResult = JSON.parse(storedResult)
      setResult(parsedResult)
    } catch (error) {
      console.error('Failed to parse stored OCR result:', error)
      sessionStorage.removeItem('ocr_test_result')
      navigate('/app/ocr-test', { replace: true })
    }
  }, [navigate])

  const handleBackToOCR = () => {
    navigate('/app/ocr-test')
  }

  return (
    <ClientLayout
      title="OCR Result"
      breadcrumb="OCR Result"
    >
      <div className="mx-auto w-full max-w-5xl">
        <Card className="p-6">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                OCR Result
              </h1>

              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Structured data extracted from the uploaded file.
              </p>
            </div>

            <button
              type="button"
              onClick={handleBackToOCR}
              className="shrink-0 rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-[var(--color-ink)] transition hover:bg-[var(--color-canvas)]"
            >
              Back to OCR
            </button>
          </div>

          <div className="overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-5">
            <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-[var(--color-ink)]">
              {result !== null
                ? JSON.stringify(result, null, 2)
                : 'Loading result...'}
            </pre>
          </div>
        </Card>
      </div>
    </ClientLayout>
  )
}