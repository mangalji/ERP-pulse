import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'

export default function OcrTestResultPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')

  useEffect(() => {
    const result = sessionStorage.getItem(
      'ocr_test_result'
    )

    if (!result) {
      navigate('/app/ocr-test')
      return
    }

    setText(result)
  }, [navigate])

  return (
    <ClientLayout
      title="OCR Result"
      breadcrumb="OCR Result"
    >
      <div className="mx-auto w-full max-w-5xl">

        <Card className="p-6">

          <div className="mb-5">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
              OCR Result
            </h1>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Complete text extracted from the uploaded file.
            </p>
          </div>

          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-5">

            <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6 text-[var(--color-ink)]">
              {text}
            </pre>

          </div>

        </Card>

      </div>
    </ClientLayout>
  )
}