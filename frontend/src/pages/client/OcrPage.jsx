import { memo, useCallback, useMemo, useState, useRef, useEffect } from 'react'
import apiClient from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import { useToast, default as Toast } from '../../components/ui/Toast.jsx'
import { aiIntegrationApi } from '../../services/aiIntegration.js'

const OCR_PAGE_SESSION_KEY = 'ocr_page_session_state'
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

const TOP_LEVEL_KEY_SET = new Set(TOP_LEVEL_FIELDS.map((f) => f.key))
const LINE_ITEM_KEY_SET = new Set(LINE_ITEM_FIELDS.map((f) => f.key))

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

  // Handle current OCR response shape: [{ ... }]
  if (Array.isArray(source)) {
    source = source[0] || {}
  }

  // Also handle wrapped shape: { data: { ... } }
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
function AIDiagnosticGuidance({
  diagnostic,
  diagnosing,
}) {
  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-800">
          AI Resolution Guidance
        </p>

        {diagnosing && !diagnostic && (
          <span className="text-xs text-slate-500">
            Analyzing…
          </span>
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
                  {diagnostic.likely_reasons.map(
                    (reason, reasonIndex) => (
                      <p
                        key={reasonIndex}
                        className="text-sm text-[var(--color-muted)]"
                      >
                        • {reason}
                      </p>
                    ),
                  )}
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
                              {solution.steps.map(
                                (step, stepIndex) => (
                                  <p
                                    key={stepIndex}
                                    className="text-sm text-[var(--color-muted)]"
                                  >
                                    {stepIndex + 1}. {step}
                                  </p>
                                ),
                              )}
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
          We are analyzing the validation issue and preparing
          resolution guidance.
        </p>
      ) : (
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          Resolution guidance is currently unavailable.
          The validation result above is still valid.
        </p>
      )}
    </div>
  )
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

  // Normalize custom header fields by their declared datatype.
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
        next[key] = lowered === 'true' || lowered === 'yes' || lowered === '1'
      } else {
        next[key] = Boolean(value)
      }
    }
    // text and date are kept as-is (strings)
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

const FieldInput =  memo(function FieldInput({ field, value, editable, onChange }) {

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
      id={`ocr-${field.key}`}
      label={field.label}
      type={field.type}
      value={displayValue}
      step={field.type === 'number' ? 'any' : undefined}
      onChange={(event) => onChange(field.key, event.target.value)}
    />
  )
})

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
  'image/bmp',
  'image/tiff',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'text/plain',
]

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff,.docx,.xlsx,.csv,.txt,application/pdf,image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain'
const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_FILES = 200

function createPreview(file) {
  if (!file || (!isPdf(file) && !isImage(file))) {
    return null
  }
  return URL.createObjectURL(file)
}

function isImage(file) {
  return file?.type?.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp|tiff)$/i.test(file?.name || '')
}

function isPdf(file) {
  return file?.type === 'application/pdf' || /\.pdf$/i.test(file?.name || '')
}

function isDocx(file) {
  return (
    file?.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    /\.docx$/i.test(file?.name || '')
  )
}

function isSpreadsheet(file) {
  return (
    file?.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    /\.xlsx$/i.test(file?.name || '')
  )
}

function isCsv(file) {
  return (
    file?.type === 'text/csv' ||
    file?.type === 'application/csv' ||
    /\.csv$/i.test(file?.name || '')
  )
}

function isText(file) {
  return (
    file?.type === 'text/plain' ||
    /\.txt$/i.test(file?.name || '')
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


export default function OcrPage() {

  const clearSelectedFilesAfterExtraction = useCallback(() => {
    setSelectedFiles((current) => {
      current.forEach(({ previewUrl }) => {
        if (previewUrl) {
          try {
            URL.revokeObjectURL(previewUrl)
          } catch {
            // Ignore object URL cleanup errors.
          }
        }
      })
      return []
    })
    setActiveIndex(0)
  }, [])

  const inputRef = useRef(null)
  const [selectedFiles, setSelectedFiles] = useState([])
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [results, setResults] = useState([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [dragActive, setDragActive] = useState(false)
  const [remotePreviewUrl, setRemotePreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')
  const [extractionTemplates, setExtractionTemplates] = useState([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [connection, setConnection] = useState(null)
  const [validationResult, setValidationResult] = useState(null)
  const [ocrMode, setOcrMode] = useState('single')
  const [ocrModes, setOcrModes] = useState({
    single: true,
    multiple: false,
  })

  const { toasts, addToast, removeToast } = useToast()
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [validating, setValidating] = useState(false)
  const [posting, setPosting] = useState(false)
  const validationAbortControllerRef = useRef(null)
  const postingAbortControllerRef = useRef(null)
  const [viewMode, setViewMode] = useState('fields')
  const [data, setData] = useState({})
  const [aiDiagnostics, setAiDiagnostics] = useState([])
  const [diagnosing, setDiagnosing] = useState(false)
  const [diagnosticError, setDiagnosticError] = useState('')

  const [ocrStateReady, setOcrStateReady] = useState(false)
  const restoredSessionStateRef = useRef(false)
  const restoredResultKeyRef = useRef(null)
  const initialResultEffectSkippedRef = useRef(false)

  const connectionId = connection?.id || null

  const customFieldTypes = useMemo(
    () =>
      (extractionTemplates.find(
        (template) => String(template?.id) === String(selectedTemplateId),
      )?.fields_config?.custom_fields || []).reduce((acc, field) => {
        const key = field?.key || field?.label
        if (key) acc[key] = field?.data_type || 'text'
        return acc
      }, {}),
    [extractionTemplates, selectedTemplateId],
  )

  const activeResult = results[activeIndex] ?? null

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

  const requestNetSuiteDiagnostics = useCallback(
  async (validationId, errors) => {
    if (!validationId || !connectionId || !errors?.length) {
      setAiDiagnostics([])
      setDiagnosticError('')
      return
    }

    setDiagnosing(true)
    setDiagnosticError('')

    try {
      const result =
        await aiIntegrationApi.diagnoseNetSuiteValidation({
          validation_ids: [String(validationId)],
          connection_id: connectionId,
        })

      setAiDiagnostics(
        Array.isArray(result?.diagnostics)
          ? result.diagnostics
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
    try {
      const raw = sessionStorage.getItem(
        OCR_PAGE_SESSION_KEY,
      )
      if(raw){
        const stored = JSON.parse(raw)
        restoredSessionStateRef.current = true

        setSelectedTemplateId(
          stored?.selectedTemplateId || '',
        )
        setOcrMode(
          stored?.ocrMode || 'single',
        )
        setResults(
          Array.isArray(stored?.results)
            ? stored.results
            : [],
        )
        setActiveIndex(
        Number.isInteger(stored?.activeIndex)
          ? Math.max(0, stored.activeIndex)
          : 0,
      )

      setValidationResult(
        stored?.validationResult || null,
      )

      setEditing(
        stored?.editing === true,
      )
      setViewMode(
        stored?.viewMode === 'json'
          ? 'json'
          : 'fields',
      )

      setData(
        cloneData(stored?.data),
      )

      setAiDiagnostics(
        Array.isArray(stored?.aiDiagnostics)
          ? stored.aiDiagnostics
          : [],
      )
      setDiagnosticError(
        typeof stored?.diagnosticError === 'string'
          ? stored.diagnosticError
          : '',
      )

      setError(
        typeof stored?.error === 'string'
          ? stored.error
          : '',
      )
      setPreviewError(
        typeof stored?.previewError === 'string'
          ? stored.previewError
          : '',
      )
      const restoredSelectedFiles =
        Array.isArray(stored?.selectedFiles)
          ? stored.selectedFiles
              .filter((item) => item?.filename)
              .map((item) => ({
                id:
                  item.id ||
                  `${item.filename}-${item.lastModified || 0}`,

                file: {
                  name: item.filename,
                  type: item.fileType || '',
                  size:
                    Number(item.fileSize) || 0,
                  lastModified:
                    Number(item.lastModified) || 0,
                },

                previewUrl: null,
              }))
          : []

      setSelectedFiles(
        restoredSelectedFiles,
      )

      const restoredResults =
        Array.isArray(stored?.results)
          ? stored.results
          : []

      const restoredIndex =
        Number.isInteger(stored?.activeIndex)
          ? Math.max(
              0,
              Math.min(
                stored.activeIndex,
                Math.max(
                  restoredResults.length - 1,
                  0,
                ),
              ),
            )
          : 0

      const restoredResult =
        restoredResults[restoredIndex] || null

      restoredResultKeyRef.current =
        restoredResult
          ? `${restoredResult.upload_id || ''}:${restoredResult.document_id || ''}:${restoredResult.version_id || ''}`
          : null
    }
  } catch (err) {
    console.error(
      'Failed to restore OCR page state:',
      err,
    )

    sessionStorage.removeItem(
      OCR_PAGE_SESSION_KEY,
    )
  } finally {
    setOcrStateReady(true)
  }
}, [])

useEffect(() => {
    if (!ocrStateReady) return

    const serializeSelectedFiles = selectedFiles.map(({ id, file }) => ({
      id,
      filename: file?.name || '',
      fileType: file?.type || '',
      fileSize: Number(file?.size) || 0,
      lastModified: Number(file?.lastModified) || 0,
    }))

    const snapshot = {
      version: 1,
      selectedFiles: serializeSelectedFiles,
      selectedTemplateId,
      ocrMode,
      results,
      activeIndex,
      validationResult,
      editing,
      viewMode,
      data,
      aiDiagnostics,
      diagnosticError,
      error,
      previewError,
    }

    try {
      sessionStorage.setItem(
        OCR_PAGE_SESSION_KEY,
        JSON.stringify(snapshot),
      )
    } catch (err) {
      console.error('Failed to persist OCR page state:', err)
    }
  }, [
    ocrStateReady,
    selectedFiles,
    selectedTemplateId,
    ocrMode,
    results,
    activeIndex,
    validationResult,
    editing,
    viewMode,
    data,
    aiDiagnostics,
    diagnosticError,
    error,
    previewError,
  ])

  useEffect(() => {
    if (!ocrStateReady) return

    const resultKey = activeResult
      ? `${activeResult.upload_id || ''}:${activeResult.document_id || ''}:${activeResult.version_id || ''}`
      : ''

    if (!initialResultEffectSkippedRef.current) {
      initialResultEffectSkippedRef.current = true
      return
    }

    if (restoredResultKeyRef.current && restoredResultKeyRef.current === resultKey) {
      restoredResultKeyRef.current = null
      return
    }

    setEditing(false)
    setSaving(false)
    setViewMode('fields')
    setData(cloneData(activeResult?.data))
    setValidationResult(null)
    setAiDiagnostics([])
    setDiagnosing(false)
    setDiagnosticError('')
  }, [ocrStateReady, activeResult?.upload_id, activeResult?.document_id, activeResult?.version_id])

  useEffect(() => {
    const clearOcrPageSession = () => {
      sessionStorage.removeItem(OCR_PAGE_SESSION_KEY)
    }

    const isOcrPath = (pathname) => pathname === '/app/ocr'

    const originalPushState = window.history.pushState
    const originalReplaceState = window.history.replaceState

    window.history.pushState = function pushStateWithOcrCleanup(state, title, url) {
      if (url != null) {
        const nextUrl = new URL(String(url), window.location.href)
        if (!isOcrPath(nextUrl.pathname)) {
          clearOcrPageSession()
        }
      }
      return originalPushState.apply(this, [state, title, url])
    }

    window.history.replaceState = function replaceStateWithOcrCleanup(state, title, url) {
      if (url != null) {
        const nextUrl = new URL(String(url), window.location.href)
        if (!isOcrPath(nextUrl.pathname)) {
          clearOcrPageSession()
        }
      }
      return originalReplaceState.apply(this, [state, title, url])
    }

    const handlePopState = () => {
      if (!isOcrPath(window.location.pathname)) {
        clearOcrPageSession()
      }
    }

    const handleDocumentClick = (event) => {
      if (event.defaultPrevented || event.button !== 0) return
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

      const anchor = event.target?.closest?.('a[href]')
      if (!anchor) return

      const href = anchor.getAttribute('href')
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return

      const nextUrl = new URL(href, window.location.href)
      if (nextUrl.origin === window.location.origin && !isOcrPath(nextUrl.pathname)) {
        clearOcrPageSession()
      }
    }

    window.addEventListener('popstate', handlePopState)
    document.addEventListener('click', handleDocumentClick, true)

    return () => {
      window.history.pushState = originalPushState
      window.history.replaceState = originalReplaceState
      window.removeEventListener('popstate', handlePopState)
      document.removeEventListener('click', handleDocumentClick, true)
    }
  }, [])

  useEffect(() => {
  const cancelActiveRequests = () => {
    validationAbortControllerRef.current?.abort()
    postingAbortControllerRef.current?.abort()

    validationAbortControllerRef.current = null
    postingAbortControllerRef.current = null

    setValidating(false)
    setPosting(false)
  }

  window.addEventListener('pagehide', cancelActiveRequests)

  return () => {
    cancelActiveRequests()
    window.removeEventListener('pagehide', cancelActiveRequests)
  }
}, [])


  const lineItems = useMemo(
    () => (Array.isArray(data.line_items) ? data.line_items : []),
    [data.line_items],
  )

  // Custom / extra header fields (anything returned by OCR that is not a
  // standard top-level field) are rendered generically so they survive the
  // review/save flow visibly rather than only inside the raw JSON view.
  const extraHeaderFields = useMemo(() => {
    if (!data || typeof data !== 'object') return []
    return Object.keys(data).filter(
      (key) => key !== 'line_items' && !TOP_LEVEL_KEY_SET.has(key),
    )
  }, [data])

  const extraLineKeys = useMemo(() => {
    const keys = new Set()
    ;(Array.isArray(data?.line_items) ? data.line_items : []).forEach((item) => {
      if (item && typeof item === 'object') {
        Object.keys(item).forEach((key) => {
          if (!LINE_ITEM_KEY_SET.has(key)) keys.add(key)
        })
      }
    })
    return Array.from(keys)
  }, [data?.line_items])

  const setField = useCallback((key, value) => {
    setData((current) => ({
      ...current,
      [key]: value,
    }))
  },[])

  const setLineItemField = useCallback((index, key, value) => {
    setData((current) => {
      const nextItems = Array.isArray(current.line_items)
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
  },[])

  const addLineItem = useCallback(() => {
    setData((current) => ({
      ...current,
      line_items: [
        ...(Array.isArray(current.line_items) ? current.line_items : []),
        emptyLineItem(),
      ],
    }))
  },[])

  const removeLineItem = useCallback((index) => {
    setData((current) => ({
      ...current,
      line_items: (Array.isArray(current.line_items)
        ? current.line_items
        : []
      ).filter((_, itemIndex) => itemIndex !== index),
    }))
  },[])

  const handleSave = async () => {
    if (!activeResult?.upload_id && !activeResult?.document_id) {
      addToast('OCR result cannot be saved because its identifier is missing.', 'error')
      return
    }

    try {
      setSaving(true)

      const payload = {
        data: normalizeEditedData(data, customFieldTypes),
      }

      if (activeResult.document_id) {
        payload.document_id = activeResult.document_id
      } else {
        payload.upload_id = activeResult.upload_id
      }

      const response = await apiClient.post('/ocr/review/save/', payload)
      const responseData = response?.data?.data ?? response?.data ?? {}

      const savedResult = {
        ...activeResult,
        document_id: responseData?.document_id || activeResult.document_id || null,
        upload_id: responseData?.upload_id || activeResult.upload_id || null,

        version_id: responseData?.version_id || activeResult.version_id || null,
        version_number:
          responseData?.version_number || activeResult.version_number || null,

        status: responseData?.status || 'APPROVED',
        data: responseData?.data || payload.data,
      }
      setResults((current) =>
        current.map((item, index) =>
          index === activeIndex ? { ...item, ...savedResult } : item,
        ),
      )
      

      setData(cloneData(savedResult.data))
      setEditing(false)
      addToast('OCR result saved successfully.')
      return savedResult

    } catch (err) {
      console.error('Failed to save OCR result:', err)

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
  if (
    !activeResult?.upload_id &&
    !activeResult?.document_id
  ) {
    addToast(
      'The OCR document is missing.',
      'error',
    )
    return
  }

  if (!connectionId) {
    addToast(
      'A NetSuite connection is required before validation.',
      'error',
    )
    return
  }

  const controller = new AbortController()
  validationAbortControllerRef.current = controller
  setValidating(true)

  try {
    const savedResult = await handleSave()

    if (controller.signal.aborted) {
      return
    }

    const documentId =
      savedResult?.document_id ||
      activeResult.document_id


    const validation =
      await netsuiteApi.validateDocument(
        documentId,
        connectionId,
        {
          signal: controller.signal,
        },
      )
      if (controller.signal.aborted){
        return
      }

    setValidationResult(validation)

    if (
      validation?.validation_id &&
      validation?.errors?.length
    ) {
      if (controller.signal.aborted){
        return
      }
      await requestNetSuiteDiagnostics(
        validation.validation_id,
        validation.errors,
      )
      if (controller.signal.aborted){
        return
      }
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
    const cancelled =
      err?.code === 'ERR_CANCELED' ||
      err?.name === 'CanceledError' ||
      controller?.signal?.aborted

    if (cancelled) {
      return
    }

    console.error(
      'Save & Validate failed:',
      err,
    )
  } finally {
    setValidating(false)

    if (
      validationAbortControllerRef.current === controller
    ) {
      validationAbortControllerRef.current = null
    }
  }
}

  const handleValidateAgain = async () => {
    setAiDiagnostics([])
    setDiagnosticError('')

    await handleSaveAndValidate()
  }

  const handlePost = async () => {
  if (!activeResult?.document_id) {
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

  const controller = new AbortController()

  postingAbortControllerRef.current = controller
  setPosting(true)
  
  try {
    const connectionData = await loadNetSuiteConnection()
    if (controller.signal.aborted){
      return
    }
    const activeConnectionId =
      connectionData?.id || connectionId

    if (!activeConnectionId) {
      addToast(
        'A NetSuite connection is required before posting.',
        'error',
      )
      return
    }
    if (controller.signal.aborted) {
      return
    }

    await netsuiteApi.postOCRVendorBill(
      activeResult.document_id,
      activeConnectionId,
      {
        signal: controller.signal,
      },
    )

    if (controller.signal.aborted) {
      return
    }

    addToast(
      'Vendor Bill posted to NetSuite.',
      'success',
    )
  } catch (err) {
    const cancelled =
      err?.code === 'ERR_CANCELED' ||
      err?.name === 'CanceledError' ||
      controller?.signal?.aborted

    if (cancelled) {
      return
    }

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

    if (
      postingAbortControllerRef.current === controller
    ) {
      postingAbortControllerRef.current = null
    }
  }
}
  
  const loadNetSuiteConnection = useCallback(async () => {
  if (connection) return connection

  try {
    const payload = await netsuiteApi.getMyConnection()
    const connectionData = payload?.data ?? payload ?? null
    setConnection(connectionData)
    return connectionData
  } catch (err) {
    console.warn('No NetSuite connection available:', err)
    setConnection(null)
    return null
  }
}, [connection])
useEffect(() => {
  loadNetSuiteConnection()
}, [loadNetSuiteConnection])

  const selectedFilesRef = useRef([])

  useEffect(() => {
    selectedFilesRef.current = selectedFiles
  },[selectedFiles])

  useEffect(() => {
    return () => {
      selectedFilesRef.current.forEach(({ previewUrl }) => {
        if (previewUrl) {
          try {
            URL.revokeObjectURL(previewUrl)
          } catch {
            // Ignore cleanup errors.
          }
        }
      })
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadExtractionTemplates = async () => {
      try {
        const response = await apiClient.get('/ocr/extraction-templates/')
        const payload = response?.data?.data ?? response?.data ?? {}
        const templates = Array.isArray(payload) ? payload : []

        if (!cancelled) {
          setExtractionTemplates(templates)

          const preferredTemplate = templates.find(
              (template) => template.is_preferred === true
          )
          if (preferredTemplate && !restoredSessionStateRef.current) {
              setSelectedTemplateId(
                  String(preferredTemplate.id)
              )
          }
        }
      } catch (err) {
        console.error('Failed to load OCR extraction templates:', err)
        if (!cancelled) {
          setExtractionTemplates([])
        }
      }
    }

    loadExtractionTemplates()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadOcrModes = async () => {
      try {
        const response = await apiClient.get('/ocr/extract/upload-modes/')
        const payload = response?.data ?? {}

        if (cancelled) return

        const singleEnabled = payload?.single?.enabled !== false
        const multipleEnabled = payload?.multiple?.enabled === true

        setOcrModes({
          single: singleEnabled,
          multiple: multipleEnabled,
        })

      } catch (err) {
        console.error('Failed to load OCR upload modes:', err)

        if (!cancelled) {
          setOcrModes({
            single: true,
            multiple: false,
          })
        }
      }
    }

    loadOcrModes()

    return () => {
      cancelled = true
    }
  }, [])

  const validateFiles = useCallback((files) => {
    const incoming = Array.from(files || [])

    if (!incoming.length) {
      return { files: [], error: 'Please select at least one document file.' }
    }

    if (incoming.length > MAX_FILES) {
      return {
        files: [],
        error: `You can upload a maximum of ${MAX_FILES} files at once.`,
      }
    }

    const validated = []

    for (const file of incoming) {
      if (!ALLOWED_TYPES.includes(file.type)) {
        return {
          files: [],
          error: `${file.name}: unsupported file type.`,
        }
      }

      if (file.size <= 0) {
        return {
          files: [],
          error: `${file.name}: file is empty.`,
        }
      }

      if (file.size > MAX_FILE_SIZE) {
        return {
          files: [],
          error: `${file.name}: file size exceeds 10 MB.`,
        }
      }

      const category = getFileCategory(file)
      const limit = category === 'Text' ? 5 * 1024 * 1024 : MAX_FILE_SIZE
      if (file.size > limit) {
        return {
          files: [],
          error: `${file.name}: ${category} file size exceeds ${Math.round(limit / 1024 / 1024)} MB.`,
        }
      }

      validated.push({
        id: `${file.name}-${file.lastModified}-${Math.random()}`,
        file,
        previewUrl: createPreview(file),
      })
    }

    return { files: validated, error: '' }
  }, [])

  const addFiles = useCallback(
    (fileList) => {
      const incoming = Array.from(fileList || [])

      if (!selectedTemplateId) {
        setError('Please select a File Template before uploading files.')
        return
      }

      if (!ocrMode) {
        setError('Please select an OCR mode before uploading files.')
        return
      }

      if (!incoming.length) return

      if (ocrMode === 'single') {
        if (incoming.length > 1) {
          setError('Single mode allows only one file at a time.')
          return
        }

        const { files, error: validationError } = validateFiles(incoming)

        if (validationError) {
          setError(validationError)
          return
        }

        selectedFiles.forEach(({ previewUrl }) => {
          if (previewUrl) {
            URL.revokeObjectURL(previewUrl)
          }
        })

        setError('')
        setSelectedFiles(files)
        setResults([])
        setActiveIndex(0)
        return
      }

      const remainingSlots = MAX_FILES - selectedFiles.length

      if (remainingSlots <= 0) {
        setError(
          `You can upload a maximum of ${MAX_FILES} files at once.`,
        )
        return
      }

      const limitedIncoming = incoming.slice(0, remainingSlots)
      const { files, error: validationError } =
        validateFiles(limitedIncoming)

      if (validationError) {
        setError(validationError)
        return
      }

      setError('')
      setSelectedFiles((current) => {
        const existingKeys = new Set(
          current.map(
            ({ file }) =>
              `${file.name}-${file.size}-${file.lastModified}`,
          ),
        )

        const merged = [...current]

        for (const item of files) {
          const key = `${item.file.name}-${item.file.size}-${item.file.lastModified}`

          if (!existingKeys.has(key)) {
            merged.push(item)
            existingKeys.add(key)
          } else {
            URL.revokeObjectURL(item.previewUrl)
          }
        }

        return merged
      })

      setResults([])
      setActiveIndex(0)
    },
    [ocrMode, selectedFiles, selectedTemplateId, validateFiles],
  )


  const handleFileChange = (event) => {
    addFiles(event.target.files)
    event.target.value = ''
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragActive(false)
    addFiles(event.dataTransfer.files)
  }

  const removeSelectedFile = (index) => {
    setSelectedFiles((current) => {
      const target = current[index]

      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl)
      }

      return current.filter((_, itemIndex) => itemIndex !== index)
    })

    setResults([])
    setActiveIndex(0)
    setError('')
  }

  const clearSelection = () => {
    selectedFiles.forEach(({ previewUrl }) => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    })

    setSelectedFiles([])
    setResults([])
    setActiveIndex(0)
    setError('')
  }

  const handleExtract = async () => {
    if (!selectedTemplateId) {
      setError('Please select a File Template before uploading or extracting files.')
      return
    }

    if (!ocrMode) {
      setError('Please select an OCR mode before extracting files.')
      return
    }

    if (!selectedFiles.length || processing) {
      if (!selectedFiles.length) {
        setError('Please select at least one document file first.')
      }
      return
    }

    if (ocrMode === 'single' && selectedFiles.length !== 1) {
      setError('Single mode allows exactly one file.')
      return
    }

    if (ocrMode === 'multiple' && !ocrModes.multiple) {
      setError('Multiple OCR is currently unavailable.')
      return
    }

    try {
      setError('')
      setProcessing(true)
      setResults([])
      setActiveIndex(0)

      const formData = new FormData()

      selectedFiles.forEach(({ file }) => {
        formData.append('files', file)
      })

      formData.append('mode', ocrMode)
      formData.append('template_id', selectedTemplateId)

      const response = await apiClient.post(
        '/ocr/extract/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        },
      )

      const payload = response?.data ?? {}
      const batchId = payload?.batch_id

      if (!batchId) {
        throw new Error('OCR batch was created without a batch ID.')
      }

      const initialFiles = Array.isArray(payload.files)
        ? payload.files.map((item) => ({
            status: item.status || 'UPLOADED',
            upload_id: item.upload_id || null,
            filename: item.filename || null,
            data: item.data || null,
            error: item.error || null,
            preview_url: item.preview_url || null,
          }))
        : []

      setResults(initialFiles)

      if (ocrMode === 'single') {
        sessionStorage.setItem(
          'ocr_test_result',
          JSON.stringify({
            status:
              payload?.status ??
              initialFiles[0]?.status ??
              'COMPLETED',
            batch_id: batchId,
            files: initialFiles,
            template_id: selectedTemplateId || null,
          }),
        )
        return
      }

      const terminalStatuses = new Set([
        'COMPLETED',
        'PARTIAL',
        'FAILED',
      ])

      const startedAt = Date.now()
      const maxPollingMs = 30 * 60 * 1000

      while (Date.now() - startedAt < maxPollingMs) {
        const statusResponse = await apiClient.get(
          `/ocr/extract/batches/${batchId}/`,
        )

        const batch = statusResponse?.data ?? {}
        const files = Array.isArray(batch?.files)
          ? batch.files
          : []

        setResults(files)
        setActiveIndex((current) => {
          if (!files.length) return 0
          return Math.min(current, files.length - 1)
        })

        const completedOrFailed = files.some((item) =>
          ['COMPLETED', 'FAILED'].includes(item.status),
        )

        if (completedOrFailed) {
          sessionStorage.setItem(
            'ocr_test_result',
            JSON.stringify({
              status: batch?.status ?? 'PROCESSING',
              batch_id: batchId,
              files,
              template_id: selectedTemplateId || null,
            }),
          )
        }

        const allTerminal =
          files.length > 0 &&
          files.every((item) =>
            ['COMPLETED', 'FAILED'].includes(item.status),
          )

        if (allTerminal || terminalStatuses.has(batch?.status)) {
          break
        }

        await new Promise((resolve) => setTimeout(resolve, 1500))
      }

      clearSelectedFilesAfterExtraction()
    } catch (err) {
      console.error('OCR batch submission failed:', err)

      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'OCR batch processing failed.'

      setError(detail)
    } finally {
      setProcessing(false)
    }
  }
  const activeSelectedItem = selectedFiles.find(({ file }) => {
    if (!activeResult?.filename) return false

    return (
      file?.name === activeResult.filename ||
      file?.name?.toLowerCase() === activeResult.filename?.toLowerCase()
    )
  })

  const activeFile =
    results.length > 0
      ? activeSelectedItem?.file ?? 
        (activeResult?.filename
          ? {
            name: activeResult.filename,
            type: 
              activeResult.mime_type ||
              activeResult.content_type ||
              '',
          }
          : null
        )
      : selectedFiles[activeIndex]?.file ?? null

  const activePreviewUrl =
    remotePreviewUrl ??
    activeSelectedItem?.previewUrl ??
    selectedFiles[activeIndex]?.previewUrl ??
    null

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    const loadRemotePreview = async () => {
      setPreviewError('')
      setRemotePreviewUrl(null)

      if (!activeResult?.preview_url) {
        return
      }

      try {
        const response = await apiClient.get(
          activeResult.preview_url,
          { responseType: 'blob' },
        )

        if (cancelled) {
          return
        }

        objectUrl = URL.createObjectURL(response.data)
        setRemotePreviewUrl(objectUrl)
      } catch (err) {
        console.error('Failed to load OCR file preview:', err)

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
  }, [activeResult?.preview_url])

  const canSlide = results.length > 1

  const goPrevious = () => {
    if (!results.length) return

    setActiveIndex((current) =>
      current <= 0 ? results.length - 1 : current - 1,
    )
  }

  const goNext = () => {
    if (!results.length) return

    setActiveIndex((current) =>
      current >= results.length - 1 ? 0 : current + 1,
    )
  }

  const statusLabel = (status) => {
    if (!status) return 'Unknown'
    return String(status).replaceAll('_', ' ')
  }

  const statusClass = (status) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-emerald-600'
      case 'FAILED':
        return 'text-red-600'
      case 'PROCESSING':
        return 'text-amber-600'
      default:
        return 'text-[var(--color-muted)]'
    }
  }

  return (
    <ClientLayout title="OCR" breadcrumb="OCR">
      <div className="flex w-full flex-col gap-6">
        <Toast toasts={toasts} removeToast={removeToast} />
        {/* Upload / actions */}
        <Card className="p-4 sm:p-5">
          <div className="flex flex-col gap-3">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
              OCR
            </h1>

            <div
              onDragEnter={(event) => {
                event.preventDefault()
                setDragActive(true)
              }}
              onDragOver={(event) => {
                event.preventDefault()
                setDragActive(true)
              }}
              onDragLeave={(event) => {
                event.preventDefault()
                setDragActive(false)
              }}
              onDrop={handleDrop}
              className={`flex flex-wrap items-center gap-3 rounded-xl border border-dashed p-3 transition ${
                dragActive
                  ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                  : 'border-transparent bg-[var(--color-canvas)]'
              }`}
            >
              <div className="flex min-w-[300px] flex-1 items-center gap-2 sm:max-w-xl">
                <label
                  htmlFor="ocr-extraction-template"
                  className="shrink-0 text-sm font-medium text-[var(--color-ink)]"
                >
                  File Template <span className="text-red-500">*</span>
                </label>
                <select
                  id="ocr-extraction-template"
                  value={selectedTemplateId}
                  onChange={(event) => setSelectedTemplateId(event.target.value)}
                  disabled={processing}
                  required
                  className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select File Template</option>
                  {extractionTemplates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="min-w-[150px]">
                <select
                  id="ocr-processing-mode"
                  value={ocrMode}
                  onChange={(event) => {
                    const nextMode = event.target.value
                    setOcrMode(nextMode)
                    setError('')
                    setResults([])
                    setActiveIndex(0)
                  }}
                  disabled={processing}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select Mode</option>
                  <option value="single" disabled={!ocrModes.single}>Single</option>
                  <option value="multiple" disabled={!ocrModes.multiple}>Multiple</option>
                </select>
              </div>

              <input
                ref={inputRef}
                type="file"
                multiple={ocrMode === 'multiple'}
                accept={ACCEPT}
                onChange={handleFileChange}
                disabled={processing || !selectedTemplateId || !ocrMode}
                className="hidden"
              />

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  disabled={processing || !selectedTemplateId || !ocrMode}
                >
                  Choose Files
                </Button>

                {!!selectedFiles.length && (
                  <>
                    <Button
                      type="button"
                      onClick={handleExtract}
                      disabled={processing || !selectedTemplateId || !ocrMode}
                    >
                      {processing ? 'Processing...' : 'Extract'}
                    </Button>
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={clearSelection}
                      disabled={processing}
                    >
                      Clear
                    </Button>
                  </>
                )}
              </div>
              {dragActive && (
                <p className="w-full text-xs font-medium text-[var(--color-primary)]">
                  Drop files to add them
                </p>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {!!selectedFiles.length && (
              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-[var(--color-ink)]">
                    Selected files ({selectedFiles.length})
                  </p>
                </div>

                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {selectedFiles.map((item, index) => (
                    <div
                      key={item.id}
                      className={`flex items-center gap-3 rounded-xl border p-3 ${
                        index === activeIndex
                          ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                          : 'border-[var(--color-border)]'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setActiveIndex(index)}
                        className="min-w-0 flex-1 text-left"
                        disabled={processing}
                      >
                        <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                          {item.file.name}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                          {(item.file.size / 1024 / 1024).toFixed(2)} MB
                          {!isImage(item.file) && !isPdf(item.file) ? ` · ${getFileCategory(item.file)}` : ''}
                        </p>
                      </button>

                      <button
                        type="button"
                        onClick={() => removeSelectedFile(index)}
                        disabled={processing}
                        className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                        aria-label={`Remove ${item.file.name}`}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Result workspace */}
        {(selectedFiles.length > 0 || results.length > 0) && (
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left: preview */}
            <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    File Preview
                  </p>

                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {activeResult?.filename ||
                      activeFile?.name ||
                      'Select a file'}
                  </p>
                </div>

                <div className="shrink-0 text-xs font-medium text-[var(--color-muted)]">
                  {results.length
                    ? `${activeIndex + 1} / ${results.length}`
                    : selectedFiles.length
                      ? `${activeIndex + 1} / ${selectedFiles.length}`
                      : '0 / 0'}
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-canvas)] p-3">
                {previewError && (
                  <div className="max-w-md rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
                    {previewError}
                  </div>
                )}

                {!previewError &&
                  activeFile &&
                  (isPdf(activeFile) || isImage(activeFile)) &&
                  activePreviewUrl && (
                    isPdf(activeFile) ? (
                      <div className="flex min-h-full w-full flex-col gap-2">
                        <iframe
                          title={activeFile.name}
                          src={activePreviewUrl}
                          className="h-[340px] min-h-0 w-full rounded-lg border border-[var(--color-border)] bg-white"
                        />
                        <a
                          href={activePreviewUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-center text-sm font-medium text-[var(--color-primary)] hover:underline"
                        >
                          Open PDF in new tab
                        </a>
                      </div>
                    ) : (
                      <img
                        src={activePreviewUrl}
                        alt={activeFile.name}
                        className="max-h-[340px] max-w-full rounded-lg object-contain shadow-sm"
                      />
                    )
                  )}

                {!previewError &&
                  activeFile &&
                  !isPdf(activeFile) &&
                  !isImage(activeFile) && (
                    <div className="max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
                      <p className="text-sm font-semibold text-[var(--color-ink)]">
                        {activeFile.name}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {getFileCategory(activeFile)} file
                      </p>
                      <p className="mt-2 text-sm text-[var(--color-muted)]">
                        Preview is not available for this format. The file will be
                        processed server-side and extraction results will appear here.
                      </p>
                    </div>
                  )}

                {!previewError &&
                  !activeFile &&
                  !activeResult?.preview_url && (
                    <p className="text-sm text-[var(--color-muted)]">
                      Select a file to preview it.
                    </p>
                  )}

              </div>

              <div className="flex items-center justify-between border-t border-[var(--color-border)] p-4">
                <Button
                  type="button"
                  intent="secondary"
                  onClick={goPrevious}
                  disabled={!canSlide}
                >
                  ← Previous
                </Button>

                <span className="text-xs text-[var(--color-muted)]">
                  {canSlide ? 'Switch file' : 'Single file'}
                </span>

                <Button
                  type="button"
                  intent="secondary"
                  onClick={goNext}
                  disabled={!canSlide}
                >
                  Next →
                </Button>
              </div>
            </Card>

            {/* Right: OCR review */}
            <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">OCR Review</p>
                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {activeResult?.filename || activeFile?.name || 'Waiting for extraction'}
                  </p>
                </div>
                {activeResult?.status && (
                  <span className={`shrink-0 text-xs font-semibold uppercase tracking-wide ${statusClass(activeResult.status)}`}>
                    {statusLabel(activeResult.status)}
                  </span>
                )}
              </div>
              <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-surface)] p-4">
                {activeResult ? (
                  activeResult.status === 'FAILED' ? (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                      {activeResult.error || 'OCR extraction failed for this file.'}
                    </div>
                  ) : (
                    <>
      <div className="flex justify-end">
        <div className="inline-flex overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-1"
      role="group"
      aria-label="OCR output view">
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
    <pre className="min-h-[400px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4 font-mono text-xs leading-6 text-[var(--color-ink)] sm:text-sm">
      {JSON.stringify(data, null, 2)}
    </pre>
  ) : (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        {TOP_LEVEL_FIELDS.map((field) => (
          <FieldInput
            key={field.key}
            field={field}
            value={data[field.key]}
            editable={editing && !saving}
            onChange={setField}
          />
        ))}

        {extraHeaderFields.map((key) => {
          const dataType = customFieldTypes[key] || 'text'
          const field = { key, label: key, type: dataType === 'currency' ? 'number' : dataType }
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

      <Card className="overflow-hidden border border-[var(--color-border)] shadow-none">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] p-4">
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-ink)]">
              Line Items
            </h3>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              {lineItems.length} {lineItems.length === 1 ? 'row' : 'rows'}
            </p>
          </div>

          {editing && (
            <Button type="button" intent="secondary" size="sm" onClick={addLineItem} disabled={saving}>
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
                  {editing && <th className="px-4 py-3">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {lineItems.map((item, index) => (
                  <tr key={`${activeResult.upload_id || activeResult.document_id}-${index}`}>
                    {LINE_ITEM_FIELDS.map((field) => (
                      <td key={field.key} className="min-w-[150px] px-4 py-3 align-top">
                        {editing ? (
                          <input
                            type={field.type}
                            value={toInputValue(item?.[field.key])}
                            step={field.type === 'number' ? 'any' : undefined}
                            onChange={(event) =>
                              setLineItemField(index, field.key, event.target.value)
                            }
                            className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                          />
                        ) : (
                          <span className="break-words text-[var(--color-ink)]">
                            {toInputValue(item?.[field.key]) || '--'}
                          </span>
                        )}
                      </td>
                    ))}
                    {extraLineKeys.map((key) => {
                      const dataType = customFieldTypes[key] || 'text'
                      const inputType = dataType === 'currency' || dataType === 'number' ? 'number' : dataType === 'date' ? 'date' : 'text'
                      return (
                        <td key={key} className="min-w-[150px] px-4 py-3 align-top">
                          {editing ? (
                            <input
                              type={inputType}
                              value={toInputValue(item?.[key])}
                              step={inputType === 'number' ? 'any' : undefined}
                              onChange={(event) =>
                                setLineItemField(index, key, event.target.value)
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
            {editing && ' Use “Add Line Item” if a source row was missed.'}
          </div>
        )}
      </Card>
      </>
      )}
                    </>
                  )
                ) : (
                  <div className="flex min-h-[400px] items-center justify-center text-center">
                    <div>
                      <p className="text-sm font-medium text-[var(--color-ink)]">Upload files and click Extract Data</p>
                      <p className="mt-1 text-sm text-[var(--color-muted)]">The result for the active file will appear here.</p>
                    </div>
                  </div>
                )}
              </div>
              {activeResult && (
                <div className="border-t border-[var(--color-border)] p-4">
      <div
        className="flex flex-wrap items-center justify-end gap-2"
      >
              
        <Button
          type="button"
          intent="secondary"
          onClick={() => {
            setViewMode('fields')
            setEditing(true)
          }}
          disabled={editing || saving || validating || posting}
        >
          Edit
        </Button>

        <div className="relative">
          <select
            className="h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm font-medium text-[var(--color-ink)] outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            value=""
            disabled={saving || validating || posting || diagnosing}
            onChange={async (event) => {
              const action = event.target.value
            
              if (action === 'save_validate') {
                await handleSaveAndValidate()
              }
            
              if (action === 'post') {
                if (
                  String(validationResult?.status || '').toUpperCase() !== 'VALIDATED'
                ){
                  addToast(
                    'Please validate the OCR data successfully before posting to NetSuite.',
                    'error',
                  )
                  event.target.value = ''
                  return
                  }
                await handlePost()
              }
            
              event.target.value = ''
            }}
          >
            <option value="">
              {validating
                ? 'Validating...'
                : posting
                  ? 'Posting...'
                  : saving
                    ? 'Saving...'
                    : 'Actions'}
            </option>
            <option
              value="save_validate"
              disabled={
                !activeResult?.upload_id &&
                !activeResult?.document_id
              }
            >
              Save & Validate
            </option>

            <option
              value="post"
              disabled={
                String(validationResult?.status || '').toUpperCase() !== 'VALIDATED'
                }
            >
              Post to NetSuite
            </option>
          </select>
        </div>
      </div>
                </div>
              )}
            </Card>
          </div>
        )}

          {validationResult && (
            <Card className="border border-[var(--color-border)] shadow-none">
              <div className="border-b border-[var(--color-border)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-[var(--color-ink)]">
                      NetSuite Validation
                    </h2>
                    <p className="mt-1 text-sm text-[var(--color-muted)]">
                      Vendor and Item existence was checked against the connected NetSuite account.
                    </p>
                  </div>

                  <span
                    className={
                      String(validationResult?.status || '').toUpperCase() === 'VALIDATED'
                        ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                        : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
                    }
                  >
                    {String(validationResult?.status || '').toUpperCase() === 'VALIDATED'
                      ? '✓ VALIDATION SUCCESSFUL'
                      : '✕ VALIDATION FAILED'}
                  </span>
                </div>
              </div>

              <div className="p-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg border border-[var(--color-border)] p-4">
                    <p className="text-xs text-[var(--color-muted)]">Vendor</p>
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
                    <p className="text-xs text-[var(--color-muted)]">Items</p>
                    <p className="mt-1 font-medium text-[var(--color-ink)]">
                      {(validationResult.items || []).filter((item) => item?.matched).length}
                      /
                      {(validationResult.items || []).length} matched
                    </p>
                  </div>
                </div>

                {validationResult.summary && (
                  <p className="mt-3 text-xs text-[var(--color-muted)]">
                    {Number(validationResult.summary.source_rows || 0)} source rows ·{' '}
                    {Number(validationResult.summary.unique_netsuite_items || 0)} unique NetSuite items ·{' '}
                    {Number(validationResult.summary.matched_rows || 0)} matched ·{' '}
                    {Number(validationResult.summary.unmatched_rows || 0)} unmatched
                  </p>
                )}

                {String(validationResult?.status || '').toUpperCase() === 'VALIDATED' ? (
                  <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                    <p className="text-sm font-semibold text-emerald-900">
                      Validation successful
                    </p>
                    <p className="mt-1 text-sm text-emerald-800">
                      The OCR data has been successfully validated against NetSuite and is ready to post.
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
                              {validationResult.errors.length === 1 ? 'issue' : 'issues'} found
                            </p>
                          </div>
                          <span className="rounded-full bg-red-100 px-2.5 py-1 text-[11px] font-semibold text-red-800">
                            {validationResult.errors.length}
                          </span>
                        </div>

                        <div className="mt-3 divide-y divide-red-200 rounded-md border border-red-200 bg-white">
                          {validationResult.errors.map((errorItem, errorIndex) => (
                            <div
                              key={`${errorItem?.type || 'error'}-${errorIndex}`}
                              className="px-3 py-3"
                            >
                              <div className="flex items-start gap-3">
                                <span className="mt-0.5 shrink-0 text-red-600">✕</span>
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-sm font-medium text-red-900">
                                      {errorItem?.message || 'Validation error'}
                                    </p>
                                    {errorItem?.type && (
                                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800">
                                        {String(errorItem.type)}
                                      </span>
                                    )}
                                  </div>
                                  {errorItem?.extracted_name && (
                                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                                      Affected value: {errorItem.extracted_name}
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
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="mt-5 text-sm text-[var(--color-muted)]">
                        NetSuite validation failed, but no detailed validation errors were returned.
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
      </div>
      </ClientLayout>
  )
}