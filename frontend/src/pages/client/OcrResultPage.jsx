import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '../../services/apiClient.js'
import { useToast, default as Toast } from '../../components/ui/Toast.jsx'
import { aiIntegrationApi } from '../../services/aiIntegration.js'
import { netsuiteApi } from '../../services/netsuite.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'

const TOP_LEVEL_FIELDS = [
  { key: 'invoice_number', label: 'Invoice Number', type: 'text' },
  { key: 'invoice_date', label: 'Invoice Date', type: 'date' },
  { key: 'due_date', label: 'Due Date', type: 'date' },
  { key: 'vendor_name', label: 'Vendor Name', type: 'text' },
  { key: 'customer_name', label: 'Customer Name', type: 'text' },
  { key: 'subsidiary', label: 'Subsidiary', type: 'text' },
  { key: 'currency', label: 'Currency', type: 'text' },
  { key: 'subtotal', label: 'Subtotal', type: 'number' },
  { key: 'tax_amount', label: 'Tax Amount', type: 'number' },
  { key: 'tax_rate', label: 'Tax Rate (%)', type: 'number' },
  { key: 'total_amount', label: 'Total Amount', type: 'number' },
  { key: 'payment_terms', label: 'Payment Terms', type: 'text' },
]

const LINE_ITEM_FIELDS = [
  { key: 'description', label: 'Description', type: 'text' },
  { key: 'quantity', label: 'Qty', type: 'number' },
  { key: 'unit_price', label: 'Unit Price', type: 'number' },
  { key: 'amount', label: 'Amount', type: 'number' },
]

const TOP_LEVEL_KEY_SET = new Set(TOP_LEVEL_FIELDS.map((field) => field.key))
const LINE_ITEM_KEY_SET = new Set(LINE_ITEM_FIELDS.map((field) => field.key))

function emptyLineItem() {
  return {
    description: null,
    quantity: null,
    unit_price: null,
    amount: null,
  }
}

function cloneData(data) {
  if (!data || typeof data !== 'object') return {}

  let source = data

  if (Array.isArray(source)) {
    source = source[0] || {}
  }

  if (
    source &&
    typeof source === 'object' &&
    !Array.isArray(source.data) &&
    source.data &&
    typeof source.data === 'object'
  ) {
    source = source.data
  }

  return JSON.parse(JSON.stringify(source))
}

function toInputValue(value) {
  return value === null || value === undefined ? '' : String(value)
}

function normalizeEditedData(data, customFieldTypes = {}) {
  const next = cloneData(data)

  TOP_LEVEL_FIELDS.forEach(({ key, type }) => {
    const value = next[key]

    if (type === 'number') {
      if (value === '' || value === null || value === undefined) {
        next[key] = null
      } else {
        const parsed = Number(value)
        next[key] = Number.isFinite(parsed) ? parsed : null
      }
      return
    }

    if (value === '') {
      next[key] = null
    }
  })

  Object.keys(customFieldTypes).forEach((key) => {
    if (!(key in next)) return

    const dataType = customFieldTypes[key]
    const value = next[key]

    if (value === '' || value === null || value === undefined) {
      next[key] = null
      return
    }

    if (dataType === 'number' || dataType === 'currency') {
      const parsed = Number(value)
      next[key] = Number.isFinite(parsed) ? parsed : null
    } else if (dataType === 'boolean') {
      if (typeof value === 'string') {
        const lowered = value.trim().toLowerCase()
        next[key] =
          lowered === 'true' ||
          lowered === 'yes' ||
          lowered === '1'
      } else {
        next[key] = Boolean(value)
      }
    }
  })

  next.line_items = Array.isArray(next.line_items)
    ? next.line_items.map((item) => {
        const normalized = { ...emptyLineItem(), ...(item || {}) }

        LINE_ITEM_FIELDS.forEach(({ key, type }) => {
          if (type === 'number') {
            if (
              normalized[key] === '' ||
              normalized[key] === null ||
              normalized[key] === undefined
            ) {
              normalized[key] = null
            } else {
              const parsed = Number(normalized[key])
              normalized[key] = Number.isFinite(parsed) ? parsed : null
            }
          } else if (normalized[key] === '') {
            normalized[key] = null
          }
        })

        return normalized
      })
    : []

  return next
}

function getFileName(file) {
  return file?.name || file?.filename || ''
}

function isImage(file) {
  return (
    file?.type?.startsWith('image/') ||
    /\.(png|jpe?g|webp|gif|bmp|tiff)$/i.test(getFileName(file))
  )
}

function isPdf(file) {
  return (
    file?.type === 'application/pdf' ||
    /\.pdf$/i.test(getFileName(file))
  )
}

function isDocx(file) {
  return (
    file?.type ===
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    /\.docx$/i.test(getFileName(file))
  )
}

function isSpreadsheet(file) {
  return (
    file?.type ===
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    /\.xlsx$/i.test(getFileName(file))
  )
}

function isCsv(file) {
  return (
    file?.type === 'text/csv' ||
    file?.type === 'application/csv' ||
    /\.csv$/i.test(getFileName(file))
  )
}

function isText(file) {
  return (
    file?.type === 'text/plain' ||
    /\.txt$/i.test(getFileName(file))
  )
}

function getFileCategory(file) {
  if (isPdf(file)) return 'PDF'
  if (isDocx(file)) return 'DOCX'
  if (isImage(file)) return 'Image'
  if (isSpreadsheet(file)) return 'Spreadsheet'
  if (isCsv(file)) return 'CSV'
  if (isText(file)) return 'Text'
  return 'Document'
}

const FieldInput = memo(function FieldInput({
  field,
  value,
  editable,
  onChange,
}) {
  const displayValue = toInputValue(value)

  if (!editable) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-ink-soft)]">
          {field.label}
        </span>
        <div className="min-h-[46px] rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3.5 py-2.5 text-sm text-[var(--color-ink)]">
          {displayValue || '--'}
        </div>
      </div>
    )
  }

  return (
    <Input
      id={`ocr-history-${field.key}`}
      label={field.label}
      type={field.type}
      value={displayValue}
      step={field.type === 'number' ? 'any' : undefined}
      onChange={(event) => onChange(field.key, event.target.value)}
    />
  )
})

function AIDiagnosticGuidance({ diagnostic, diagnosing }) {
  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-800">
          AI Resolution Guidance
        </p>
        {diagnosing && !diagnostic && (
          <span className="text-xs text-slate-500">Analyzing…</span>
        )}
      </div>

      {diagnostic ? (
        <div className="mt-3 space-y-4">
          {/* AI returns only likely reasons and possible solutions. */}
          {Array.isArray(diagnostic.likely_reasons) &&
            diagnostic.likely_reasons.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Likely Reasons
                </p>
                <div className="mt-2 space-y-1">
                  {diagnostic.likely_reasons.map((reason, reasonIndex) => (
                    <p
                      key={reasonIndex}
                      className="text-sm text-[var(--color-muted)]"
                    >
                      • {reason}
                    </p>
                  ))}
                </div>
              </div>
            )}

          {Array.isArray(diagnostic.possible_solutions) &&
            diagnostic.possible_solutions.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  How to Resolve It
                </p>
                <div className="mt-2 grid gap-3 md:grid-cols-3">
                  {diagnostic.possible_solutions.map(
                    (solution, solutionIndex) => (
                      <div
                        key={solutionIndex}
                        className="rounded-md border border-slate-200 bg-white p-3"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-sm font-semibold text-[var(--color-ink)]">
                            {solution.title}
                          </p>
                          {solution.recommended && (
                            <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-semibold text-emerald-700">
                              Recommended
                            </span>
                          )}
                        </div>

                        {Array.isArray(solution.steps) &&
                          solution.steps.length > 0 && (
                            <div className="mt-2 space-y-1">
                              {solution.steps.map((step, stepIndex) => (
                                <p
                                  key={stepIndex}
                                  className="text-sm text-[var(--color-muted)]"
                                >
                                  {stepIndex + 1}. {step}
                                </p>
                              ))}
                            </div>
                          )}

                        {solution.reason && (
                          <p className="mt-2 line-clamp-2 text-xs text-[var(--color-muted)]">
                            {solution.reason}
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </div>
            )}
            {/* Additional checks are intentionally omitted to keep AI diagnostics concise. */}
        </div>
      ) : diagnosing ? (
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          We are analyzing the validation issue and preparing resolution
          guidance.
        </p>
      ) : (
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          Resolution guidance is currently unavailable. The validation result
          above is still valid.
        </p>
      )}
    </div>
  )
}

export default function OcrResultPage() {
  const navigate = useNavigate()
  const { documentId } = useParams()

  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [remotePreviewUrl, setRemotePreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')
  const [customFieldTypes, setCustomFieldTypes] = useState({})
  const [connection, setConnection] = useState(null)
  const [validationResult, setValidationResult] = useState(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [posting, setPosting] = useState(false)
  const [viewMode, setViewMode] = useState('fields')
  const [data, setData] = useState({})
  const [aiDiagnostics, setAiDiagnostics] = useState([])
  const [diagnosing, setDiagnosing] = useState(false)
  const [diagnosticError, setDiagnosticError] = useState('')

  const { toasts, addToast, removeToast } = useToast()
  const connectionId = connection?.id || null

  const customFieldKeys = useMemo(
    () => new Set(Object.keys(customFieldTypes)),
    [customFieldTypes],
  )

  const aiDiagnosticsByReference = useMemo(
    () =>
      new Map(
        (aiDiagnostics || []).map((diagnostic) => [
          diagnostic.error_reference,
          diagnostic,
        ]),
      ),
    [aiDiagnostics],
  )

  const lineItems = useMemo(
    () => (Array.isArray(data?.line_items) ? data.line_items : []),
    [data?.line_items],
  )

  const extraHeaderFields = useMemo(() => {
    if (!data || typeof data !== 'object') return []

    return Object.keys(data).filter(
      (key) =>
        key !== 'line_items' &&
        !TOP_LEVEL_KEY_SET.has(key) &&
        !customFieldKeys.has(key),
    )
  }, [customFieldKeys, data])

  const templateHeaderFields = useMemo(() => {
    const configured = Object.keys(customFieldTypes)

    return configured.filter(
      (key) => key in data && key !== 'line_items',
    )
  }, [customFieldTypes, data])

  const extraLineKeys = useMemo(() => {
    const keys = new Set()

    lineItems.forEach((item) => {
      if (!item || typeof item !== 'object') return
      Object.keys(item).forEach((key) => {
        if (!LINE_ITEM_KEY_SET.has(key)) keys.add(key)
      })
    })

    return Array.from(keys)
  }, [lineItems])

  const loadNetSuiteConnection = useCallback(async () => {
    if (connection) return connection

    try {
      const payload = await netsuiteApi.getMyConnection()
      const connectionData = payload?.data ?? payload ?? null
      setConnection(connectionData)
      return connectionData
    } catch (err) {
      console.warn(
        'No NetSuite connection available for OCR history:',
        err,
      )
      setConnection(null)
      return null
    }
  }, [connection])

  useEffect(() => {
    loadNetSuiteConnection()
  }, [loadNetSuiteConnection])

  const requestNetSuiteDiagnostics = useCallback(
    async (validationId, errors, activeConnectionId = connectionId) => {
      if (
        !validationId ||
        !activeConnectionId ||
        !errors?.length
      ) {
        setAiDiagnostics([])
        setDiagnosticError('')
        return
      }

      setDiagnosing(true)
      setDiagnosticError('')

      try {
        const diagnosticResult =
          await aiIntegrationApi.diagnoseNetSuiteValidation({
            validation_ids: [String(validationId)],
            connection_id: activeConnectionId,
          })

        setAiDiagnostics(
          Array.isArray(diagnosticResult?.diagnostics)
            ? diagnosticResult.diagnostics
            : [],
        )
      } catch (err) {
        console.error(
          'NetSuite resolution guidance failed:',
          err,
        )

        setAiDiagnostics([])
        const detail = err?.response?.data?.detail
        setDiagnosticError(
          detail
          || 'We could not prepare AI resolution guidance right now. Please try again.',
        )
      } finally {
        setDiagnosing(false)
      }
    },
    [connectionId],
  )

  useEffect(() => {
    const loadResult = async () => {
      if (!documentId) {
        setError('No OCR document was selected.')
        return
      }

      try {
        setLoading(true)
        setError('')

        const response = await apiClient.get(
          `/ocr/documents/${documentId}/history/`,
        )

        const payload = response?.data?.data ?? response?.data ?? {}
        const versions = Array.isArray(payload?.versions)
          ? payload.versions
          : []

        if (!versions.length) {
          throw new Error('No saved OCR version was found.')
        }

        const latest = [...versions].sort(
          (a, b) =>
            (b.version_number ?? 0) - (a.version_number ?? 0),
        )[0]

        const reviewedData =
          latest?.reviewed_json &&
          typeof latest.reviewed_json === 'object' &&
          Object.keys(latest.reviewed_json).length
            ? latest.reviewed_json
            : latest?.normalized_json ?? {}

        const customFields = payload?.requested_fields?.custom_fields || []

        const customTypes = customFields.reduce((acc, field) => {
          const key = field?.key || field?.label
          if (key) {
            acc[key] = field?.data_type || 'text'
          }
          return acc
        }, {})

        setCustomFieldTypes(customTypes)

        const loadedResult = {
          status: payload.status || 'APPROVED',
          upload_id: payload.upload_id || null,
          document_id: payload.id || documentId,
          version_id: latest.id || null,
          version_number: latest.version_number || null,
          filename: payload.filename || 'OCR document',
          preview_url: payload.upload_id
            ? `/ocr/extract/uploads/${payload.upload_id}/preview/`
            : null,
          data: reviewedData,
        }

        setResult(loadedResult)
        setData(cloneData(reviewedData))
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
  }, [documentId])

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

  const setField = useCallback((key, value) => {
    setData((current) => ({
      ...current,
      [key]: value,
    }))
  }, [])

  const setLineItemField = useCallback((index, key, value) => {
    setData((current) => {
      const nextItems = Array.isArray(current?.line_items)
        ? [...current.line_items]
        : []

      nextItems[index] = {
        ...emptyLineItem(),
        ...(nextItems[index] || {}),
        [key]: value,
      }

      return {
        ...current,
        line_items: nextItems,
      }
    })
  }, [])

  const addLineItem = useCallback(() => {
    setData((current) => ({
      ...current,
      line_items: [
        ...(Array.isArray(current?.line_items)
          ? current.line_items
          : []),
        emptyLineItem(),
      ],
    }))
  }, [])

  const removeLineItem = useCallback((index) => {
    setData((current) => ({
      ...current,
      line_items: (Array.isArray(current?.line_items)
        ? current.line_items
        : []
      ).filter((_, itemIndex) => itemIndex !== index),
    }))
  }, [])

  const handleSave = async () => {
    if (!result?.document_id) {
      addToast(
        'The OCR document is missing.',
        'error',
      )
      return
    }

    try {
      setSaving(true)

      const payload = {
        document_id: result.document_id,
        data: normalizeEditedData(
          data,
          customFieldTypes,
        ),
      }

      const response = await apiClient.post(
        '/ocr/review/save/',
        payload,
      )

      const responseData =
        response?.data?.data ??
        response?.data ??
        {}

      const savedResult = {
        ...result,
        document_id:
          responseData?.document_id ||
          result.document_id,
        upload_id:
          responseData?.upload_id ||
          result.upload_id ||
          null,
        version_id:
          responseData?.version_id ||
          result.version_id ||
          null,
        version_number:
          responseData?.version_number ||
          result.version_number ||
          null,
        status:
          responseData?.status ||
          'APPROVED',
        data:
          responseData?.data ||
          payload.data,
      }

      setResult(savedResult)
      setData(cloneData(savedResult.data))
      setEditing(false)

      addToast(
        'OCR result saved successfully.',
        'success',
      )

      return savedResult
    } catch (err) {
      console.error(
        'Failed to save OCR result:',
        err,
      )

      addToast(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to save OCR result.',
        'error',
      )

      throw err
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAndValidate = async () => {
    if (!result?.document_id) {
      addToast(
        'The OCR document is missing.',
        'error',
      )
      return
    }

    try {
      const connectionData = await loadNetSuiteConnection()
      const activeConnectionId = connectionData?.id

      if (!activeConnectionId) {
        addToast(
          'A NetSuite connection is required before validation.',
          'error',
        )
        return
      }

      const savedResult = await handleSave()

      const activeDocumentId =
        savedResult?.document_id ||
        result.document_id

      const validation =
        await netsuiteApi.validateDocument(
          activeDocumentId,
          activeConnectionId,
        )

      setValidationResult(validation)

      if (
        validation?.validation_id &&
        validation?.errors?.length
      ) {
        await requestNetSuiteDiagnostics(
          validation.validation_id,
          validation.errors,
          activeConnectionId,
        )
      }

      addToast(
        validation?.status === 'VALIDATED'
          ? 'OCR data validated successfully.'
          : 'OCR data saved. Validation found issues.',
        validation?.status === 'VALIDATED'
          ? 'success'
          : 'error',
      )
    } catch (err) {
      console.error(
        'Save & Validate failed:',
        err,
      )
    }
  }

  const handleValidateAgain = async () => {
    setAiDiagnostics([])
    setDiagnosticError('')
    await handleSaveAndValidate()
  }

  const handlePost = async () => {
    if (!result?.document_id) {
      addToast(
        'Please save the OCR data before posting it to NetSuite.',
        'error',
      )
      return
    }

    if (
      String(validationResult?.status || '').toUpperCase() !==
      'VALIDATED'
    ) {
      addToast(
        'Please validate the OCR data successfully before posting to NetSuite.',
        'error',
      )
      return
    }

    try {
      setPosting(true)

      const connectionData = await loadNetSuiteConnection()
      const activeConnectionId = connectionData?.id

      if (!activeConnectionId) {
        addToast(
          'A NetSuite connection is required before posting.',
          'error',
        )
        return
      }

      await netsuiteApi.postOCRVendorBill(
        result.document_id,
        activeConnectionId,
      )

      addToast(
        'Vendor Bill posted to NetSuite.',
        'success',
      )
    } catch (err) {
      console.error(
        'Failed to post Vendor Bill to NetSuite:',
        err,
      )

      addToast(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to post Vendor Bill to NetSuite.',
        'error',
      )
    } finally {
      setPosting(false)
    }
  }

  const previewIsPdf = isPdf(result)
  const previewIsImage = isImage(result)

  return (
    <ClientLayout title="OCR Result" breadcrumb="OCR / OCR Result">
      <div className="flex w-full flex-col gap-6">
        <Toast toasts={toasts} removeToast={removeToast} />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
              OCR Review
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Review, edit, validate and post this saved OCR document.
            </p>
          </div>

          <Button
            type="button"
            intent="secondary"
            onClick={() => navigate('/app/ocr/history')}
          >
            Back to History
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
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Left: preview */}
              <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
                <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                      File Preview
                    </p>
                    <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                      {result.filename || 'OCR document'}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs font-medium text-[var(--color-muted)]">
                    Saved Result
                  </span>
                </div>

                <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-canvas)] p-3">
                  {previewError && (
                    <div className="max-w-md rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
                      {previewError}
                    </div>
                  )}

                  {!previewError &&
                    result &&
                    (previewIsPdf || previewIsImage) &&
                    remotePreviewUrl &&
                    (previewIsPdf ? (
                      <div className="flex min-h-full w-full flex-col gap-2">
                        <iframe
                          title={result.filename || 'OCR document'}
                          src={remotePreviewUrl}
                          className="h-[340px] min-h-0 w-full rounded-lg border border-[var(--color-border)] bg-white"
                        />
                        <a
                          href={remotePreviewUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-center text-sm font-medium text-[var(--color-primary)] hover:underline"
                        >
                          Open PDF in new tab
                        </a>
                      </div>
                    ) : (
                      <img
                        src={remotePreviewUrl}
                        alt={result.filename || 'OCR document'}
                        className="max-h-[340px] max-w-full rounded-lg object-contain shadow-sm"
                      />
                    ))}

                  {!previewError &&
                    result &&
                    !previewIsPdf &&
                    !previewIsImage && (
                      <div className="max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
                        <p className="text-sm font-semibold text-[var(--color-ink)]">
                          {result.filename || 'OCR document'}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                          {getFileCategory(result)} file
                        </p>
                        <p className="mt-2 text-sm text-[var(--color-muted)]">
                          Preview is not available for this format. The saved
                          extraction result is available in the review panel.
                        </p>
                      </div>
                    )}

                  {!previewError &&
                    result &&
                    (previewIsPdf || previewIsImage) &&
                    !remotePreviewUrl && (
                      <p className="text-sm text-[var(--color-muted)]">
                        Loading file preview...
                      </p>
                    )}
                </div>
              </Card>

              {/* Right: OCR review */}
              <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
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
                  <div className="flex justify-end">
                    <div
                      className="inline-flex overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-1"
                      role="group"
                      aria-label="OCR output view"
                    >
                      <button
                        type="button"
                        onClick={() => setViewMode('json')}
                        className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                          viewMode === 'json'
                            ? 'bg-[var(--color-primary)] text-white'
                            : 'text-[var(--color-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]'
                        }`}
                        aria-pressed={viewMode === 'json'}
                      >
                        JSON
                      </button>
                      <button
                        type="button"
                        onClick={() => setViewMode('fields')}
                        className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                          viewMode === 'fields'
                            ? 'bg-[var(--color-primary)] text-white'
                            : 'text-[var(--color-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]'
                        }`}
                        aria-pressed={viewMode === 'fields'}
                      >
                        Fields
                      </button>
                    </div>
                  </div>

                  {viewMode === 'json' ? (
                    <pre className="mt-4 min-h-[400px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4 font-mono text-xs leading-6 text-[var(--color-ink)] sm:text-sm">
                      {JSON.stringify(data, null, 2)}
                    </pre>
                  ) : (
                    <>
                      <div className="mt-4 grid gap-4 sm:grid-cols-2">
                        {TOP_LEVEL_FIELDS.map((field) => (
                          <FieldInput
                            key={field.key}
                            field={field}
                            value={data[field.key]}
                            editable={editing && !saving}
                            onChange={setField}
                          />
                        ))}

                        {templateHeaderFields.map((key) => {
                          const dataType = customFieldTypes[key] || 'text'
                          const field = {
                            key,
                            label:
                              customFieldTypes[key] === 'text'
                                ? key
                                : key,
                            type:
                              dataType === 'currency'
                                ? 'number'
                                : dataType === 'boolean'
                                  ? 'text'
                                  : dataType,
                          }

                          return (
                            <FieldInput
                              key={key}
                              field={field}
                              value={data[key]}
                              editable={editing && !saving}
                              onChange={setField}
                            />
                          )
                        })}

                        {extraHeaderFields.map((key) => {
                          const field = {
                            key,
                            label: key,
                            type: 'text',
                          }

                          return (
                            <FieldInput
                              key={key}
                              field={field}
                              value={data[key]}
                              editable={editing && !saving}
                              onChange={setField}
                            />
                          )
                        })}
                      </div>

                      <Card className="mt-4 overflow-hidden border border-[var(--color-border)] shadow-none">
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] p-4">
                          <div>
                            <h3 className="text-sm font-semibold text-[var(--color-ink)]">
                              Line Items
                            </h3>
                            <p className="mt-1 text-xs text-[var(--color-muted)]">
                              {lineItems.length}{' '}
                              {lineItems.length === 1 ? 'row' : 'rows'}
                            </p>
                          </div>

                          {editing && (
                            <Button
                              type="button"
                              intent="secondary"
                              size="sm"
                              onClick={addLineItem}
                              disabled={saving}
                            >
                              Add Line Item
                            </Button>
                          )}
                        </div>

                        {lineItems.length ? (
                          <div className="overflow-x-auto">
                            <table className="min-w-[760px] w-full text-left text-sm">
                              <thead className="bg-[var(--color-canvas)] text-xs uppercase tracking-wide text-[var(--color-muted)]">
                                <tr>
                                  <th className="px-4 py-3">Description</th>
                                  <th className="px-4 py-3">Qty</th>
                                  <th className="px-4 py-3">Unit Price</th>
                                  <th className="px-4 py-3">Amount</th>
                                  {extraLineKeys.map((key) => (
                                    <th key={key} className="px-4 py-3">
                                      {key}
                                    </th>
                                  ))}
                                  {editing && (
                                    <th className="px-4 py-3">Action</th>
                                  )}
                                </tr>
                              </thead>

                              <tbody className="divide-y divide-[var(--color-border)]">
                                {lineItems.map((item, index) => (
                                  <tr
                                    key={`${result.document_id || result.upload_id}-${index}`}
                                  >
                                    {LINE_ITEM_FIELDS.map((field) => (
                                      <td
                                        key={field.key}
                                        className="min-w-[150px] px-4 py-3 align-top"
                                      >
                                        {editing ? (
                                          <input
                                            type={field.type}
                                            value={toInputValue(
                                              item?.[field.key],
                                            )}
                                            step={
                                              field.type === 'number'
                                                ? 'any'
                                                : undefined
                                            }
                                            onChange={(event) =>
                                              setLineItemField(
                                                index,
                                                field.key,
                                                event.target.value,
                                              )
                                            }
                                            className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                                          />
                                        ) : (
                                          <span className="break-words text-[var(--color-ink)]">
                                            {toInputValue(item?.[field.key]) ||
                                              '--'}
                                          </span>
                                        )}
                                      </td>
                                    ))}

                                    {extraLineKeys.map((key) => {
                                      const dataType = customFieldTypes[key] || 'text'
                                      const inputType =
                                        dataType === 'currency' || dataType === 'number'
                                          ? 'number'
                                          : dataType === 'date'
                                            ? 'date'
                                            : 'text'

                                      return (
                                        <td
                                          key={key}
                                          className="min-w-[150px] px-4 py-3 align-top"
                                        >
                                          {editing ? (
                                            <input
                                              type={inputType}
                                              value={toInputValue(item?.[key])}
                                              step={
                                                inputType === 'number' ? 'any' : undefined
                                              }
                                              onChange={(event) =>
                                                setLineItemField(
                                                  index,
                                                  key,
                                                  event.target.value,
                                                )
                                              }
                                              className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                                            />
                                          ) : (
                                            <span className="break-words text-[var(--color-ink)]">
                                              {toInputValue(item?.[key]) || '--'}
                                            </span>
                                          )}
                                        </td>
                                      )
                                    })}

                                    {editing && (
                                      <td className="px-4 py-3 align-top">
                                        <Button
                                          type="button"
                                          intent="ghost"
                                          size="sm"
                                          onClick={() => removeLineItem(index)}
                                          disabled={saving}
                                          className="text-red-600"
                                        >
                                          Remove
                                        </Button>
                                      </td>
                                    )}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="p-5 text-sm text-[var(--color-muted)]">
                            No line items were returned by OCR.
                            {editing &&
                              ' Use “Add Line Item” if a source row was missed.'}
                          </div>
                        )}
                      </Card>
                    </>
                  )}
                </div>

                <div className="border-t border-[var(--color-border)] p-4">
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={() => {
                        setViewMode('fields')
                        setEditing(true)
                      }}
                      disabled={editing || saving || posting}
                    >
                      Edit
                    </Button>

                    <div className="relative">
                      <select
                        className="h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm font-medium text-[var(--color-ink)] outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        value=""
                        disabled={saving || posting || diagnosing}
                        onChange={async (event) => {
                          const action = event.target.value

                          if (action === 'save_validate') {
                            await handleSaveAndValidate()
                          }

                          if (action === 'post') {
                            await handlePost()
                          }

                          event.target.value = ''
                        }}
                      >
                        <option value="">Actions</option>
                        <option value="save_validate">
                          Save &amp; Validate
                        </option>
                        <option
                          value="post"
                          disabled={
                            String(
                              validationResult?.status || '',
                            ).toUpperCase() !== 'VALIDATED'
                          }
                        >
                          Post to NetSuite
                        </option>
                      </select>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {validationResult && (
              <Card className="border border-[var(--color-border)] shadow-none">
                <div className="border-b border-[var(--color-border)] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-[var(--color-ink)]">
                        NetSuite Validation
                      </h2>
                      <p className="mt-1 text-sm text-[var(--color-muted)]">
                        Vendor and Item existence was checked against the
                        connected NetSuite account.
                      </p>
                    </div>

                    <span
                      className={
                        String(
                          validationResult?.status || '',
                        ).toUpperCase() === 'VALIDATED'
                          ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                          : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
                      }
                    >
                      {String(
                        validationResult?.status || '',
                      ).toUpperCase() === 'VALIDATED'
                        ? '✓ VALIDATION SUCCESSFUL'
                        : '✕ VALIDATION FAILED'}
                    </span>
                  </div>
                </div>

                <div className="p-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg border border-[var(--color-border)] p-4">
                      <p className="text-xs text-[var(--color-muted)]">
                        Vendor
                      </p>
                      <p className="mt-1 font-medium text-[var(--color-ink)]">
                        {validationResult.vendor?.matched
                          ? '✓ Found in NetSuite'
                          : '✕ Not found in NetSuite'}
                      </p>
                      {validationResult.vendor?.extracted_name && (
                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                          {validationResult.vendor.extracted_name}
                        </p>
                      )}
                    </div>

                    <div className="rounded-lg border border-[var(--color-border)] p-4">
                      <p className="text-xs text-[var(--color-muted)]">
                        Items
                      </p>
                      <p className="mt-1 font-medium text-[var(--color-ink)]">
                        {(validationResult.items || []).filter(
                          (item) => item?.matched,
                        ).length}
                        /
                        {(validationResult.items || []).length} matched
                      </p>
                    </div>
                  </div>

                  {validationResult.summary && (
                    <p className="mt-3 text-xs text-[var(--color-muted)]">
                      {Number(
                        validationResult.summary.source_rows || 0,
                      )}{' '}
                      source rows ·{' '}
                      {Number(
                        validationResult.summary.unique_netsuite_items || 0,
                      )}{' '}
                      unique NetSuite items ·{' '}
                      {Number(
                        validationResult.summary.matched_rows || 0,
                      )}{' '}
                      matched ·{' '}
                      {Number(
                        validationResult.summary.unmatched_rows || 0,
                      )}{' '}
                      unmatched
                    </p>
                  )}

                  {String(
                    validationResult?.status || '',
                  ).toUpperCase() === 'VALIDATED' ? (
                    <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                      <p className="text-sm font-semibold text-emerald-900">
                        Validation successful
                      </p>
                      <p className="mt-1 text-sm text-emerald-800">
                        The OCR data has been successfully validated against
                        NetSuite and is ready to post.
                      </p>
                    </div>
                  ) : (
                    <>
                      {(validationResult.errors || []).length > 0 ? (
                        <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-red-900">
                                Validation Errors
                              </p>
                              <p className="mt-1 text-xs text-red-700">
                                {validationResult.errors.length}{' '}
                                {validationResult.errors.length === 1
                                  ? 'issue'
                                  : 'issues'}{' '}
                                found
                              </p>
                            </div>
                            <span className="rounded-full bg-red-100 px-2.5 py-1 text-[11px] font-semibold text-red-800">
                              {validationResult.errors.length}
                            </span>
                          </div>

                          <div className="mt-3 divide-y divide-red-200 rounded-md border border-red-200 bg-white">
                            {validationResult.errors.map(
                              (errorItem, errorIndex) => (
                                <div
                                  key={`${errorItem?.type || 'error'}-${errorIndex}`}
                                  className="px-3 py-3"
                                >
                                  <div className="flex items-start gap-3">
                                    <span className="mt-0.5 shrink-0 text-red-600">
                                      ✕
                                    </span>
                                    <div className="min-w-0 flex-1">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <p className="text-sm font-medium text-red-900">
                                          {errorItem?.message ||
                                            'Validation error'}
                                        </p>
                                        {errorItem?.type && (
                                          <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800">
                                            {String(errorItem.type)}
                                          </span>
                                        )}
                                      </div>

                                      {errorItem?.extracted_name && (
                                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                                          Affected value:{' '}
                                          {errorItem.extracted_name}
                                        </p>
                                      )}

                                      <AIDiagnosticGuidance
                                        diagnostic={aiDiagnosticsByReference.get(
                                          `${validationResult?.validation_id}:${errorIndex}`,
                                        )}
                                        diagnosing={diagnosing}
                                      />
                                    </div>
                                  </div>
                                </div>
                              ),
                            )}
                          </div>
                        </div>
                      ) : (
                        <p className="mt-5 text-sm text-[var(--color-muted)]">
                          NetSuite validation failed, but no detailed
                          validation errors were returned.
                        </p>
                      )}

                      {diagnosticError && (
                        <p className="mt-3 text-xs text-amber-700">
                          {diagnosticError}
                        </p>
                      )}
                    </>
                  )}

                  <div className="mt-4 flex justify-end">
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={handleValidateAgain}
                      disabled={saving || posting || diagnosing}
                    >
                      Validate Again
                    </Button>
                  </div>
                </div>
              </Card>
            )}
          </>
        ) : (
          <Card className="p-6 text-sm text-[var(--color-muted)]">
            No OCR result found.
          </Card>
        )}
      </div>
    </ClientLayout>
  )
}
