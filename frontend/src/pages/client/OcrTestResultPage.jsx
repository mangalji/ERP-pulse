import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import { clientApi } from '../../services/client.js'

const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED'])

export default function OcrTestResultPage() {
  const { batchId } = useParams()
  const [jsonResult, setJsonResult] = useState({
    status: 'LOADING',
    message: 'Loading OCR job...',
  })

  useEffect(() => {
    let cancelled = false
    let timer

    const load = async () => {
      try {
        const batch = await clientApi.getInvoiceBatch(batchId)
        const file = batch?.files?.[0]
        const extraction = file?.extraction
        const status = batch?.status || file?.status || 'PROCESSING'

        if (cancelled) return

        if (extraction?.extracted_json != null) {
          setJsonResult(extraction.extracted_json)
          return
        }

        if (status === 'FAILED' || file?.status === 'FAILED') {
          setJsonResult({
            status: 'FAILED',
            message: 'OCR processing failed.',
          })
          return
        }

        setJsonResult({
          status: TERMINAL_STATUSES.has(status) ? status : 'PROCESSING',
          message: 'OCR processing is in progress.',
        })

        timer = window.setTimeout(load, 2000)
      } catch (err) {
        if (cancelled) return

        setJsonResult({
          status: 'FAILED',
          message: err.payload?.message || err.message || 'Failed to load OCR result.',
        })
      }
    }

    load()

    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [batchId])

  return (
    <ClientLayout title="OCR Result" breadcrumb="OCR Result">
      <div className="mx-auto w-full max-w-5xl">
        <Card className="overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-6 py-4">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
              Extracted JSON
            </h1>
          </div>

          <pre className="max-h-[70vh] overflow-auto p-6 text-sm leading-6 text-[var(--color-ink)]">
            {JSON.stringify(jsonResult, null, 2)}
          </pre>
        </Card>
      </div>
    </ClientLayout>
  )
}
