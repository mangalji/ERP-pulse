import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
]

export default function OcrTestPage() {
  const navigate = useNavigate()

  const [selectedFile, setSelectedFile] = useState(null)
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)

  const handleFileChange = (event) => {
    const file = event.target.files?.[0]

    setError('')
    setSelectedFile(null)

    if (!file) {
      return
    }

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(
        'Please select a PDF, PNG, JPG or JPEG file.'
      )
      event.target.value = ''
      return
    }

    setSelectedFile(file)
  }

  const handleExtract = async () => {
    if (!selectedFile) {
      setError('Please select a PDF or image first.')
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
        }
      )

      const extractedText = response.data

      sessionStorage.setItem(
        'ocr_test_result',
        extractedText
      )

      navigate('/app/ocr-test/result')

    } catch (err) {
      console.error('OCR test failed:', err)

      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'OCR extraction failed.'

      setError(detail)

    } finally {
      setProcessing(false)
    }
  }

  return (
    <ClientLayout
      title="OCR Test"
      breadcrumb="OCR Test"
    >
      <div className="mx-auto w-full max-w-3xl">
        <Card className="p-6">

          <div className="mb-6">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
              OCR Test
            </h1>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Upload a PDF or image and extract its complete text.
            </p>
          </div>

          <div className="rounded-lg border border-dashed border-[var(--color-border)] p-6">

            <label className="block text-sm font-medium text-[var(--color-ink)]">
              Upload PDF / Image
            </label>

            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
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
                {processing
                  ? 'Extracting...'
                  : 'Extract Data'}
              </Button>
            </div>

          </div>
        </Card>
      </div>
    </ClientLayout>
  )
}