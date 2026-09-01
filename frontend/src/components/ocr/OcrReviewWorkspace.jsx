import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Card from '../ui/Card.jsx'
import Input from '../ui/Input.jsx'
import Button from '../ui/Button.jsx'
import { useToast, default as Toast } from '../ui/Toast.jsx'
import apiClient from '../../services/apiClient.js'

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

function FieldInput({ field, value, editable, onChange }) {

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
}

export default function OcrReviewWorkspace({
  result,
  batchResults = [],
  onSaved,
  showPost = true,
  compact = false,
  customFieldTypes = {},
  connectionId = null,
  validationResult = null,
  onValidate = null,
  onPost = null,
  mappings = [],
  onSaveMappings = null,
}) {
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [posting, setPosting] = useState(false)
  const [viewMode, setViewMode] = useState('fields')
  const [data, setData] = useState({})

  useEffect(() => {
    setEditing(false)
    setSaving(false)
    setViewMode('fields')
    setData(cloneData(result?.data))
  }, [result?.upload_id, result?.document_id, result?.version_id, result?.data])

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

  const setField = (key, value) => {
    setData((current) => ({
      ...current,
      [key]: value,
    }))
  }

  const setLineItemField = (index, key, value) => {
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
  }

  const addLineItem = () => {
    setData((current) => ({
      ...current,
      line_items: [
        ...(Array.isArray(current.line_items) ? current.line_items : []),
        emptyLineItem(),
      ],
    }))
  }

  const removeLineItem = (index) => {
    setData((current) => ({
      ...current,
      line_items: (Array.isArray(current.line_items)
        ? current.line_items
        : []
      ).filter((_, itemIndex) => itemIndex !== index),
    }))
  }

  const handleSave = async () => {
    if (!result?.upload_id && !result?.document_id) {
      addToast('OCR result cannot be saved because its identifier is missing.', 'error')
      return
    }

    try {
      setSaving(true)

      const payload = {
        data: normalizeEditedData(data, customFieldTypes),
      }

      if (result.document_id) {
        payload.document_id = result.document_id
      } else {
        payload.upload_id = result.upload_id
      }

      const response = await apiClient.post('/ocr/review/save/', payload)
      const responseData = response?.data?.data ?? response?.data ?? {}

      const savedResult = {
        ...result,
        document_id: responseData?.document_id || result.document_id || null,
        upload_id: responseData?.upload_id || result.upload_id || null,

        version_id: responseData?.version_id || result.version_id || null,
        version_number:
          responseData?.version_number || result.version_number || null,

        status: responseData?.status || 'APPROVED',
        data: responseData?.data || payload.data,
      }
      onSaved?.(savedResult)

      setData(cloneData(savedResult.data))
      setEditing(false)
      addToast('OCR result saved successfully.')
    } catch (err) {
      console.error('Failed to save OCR result:', err)
      addToast(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to save OCR result.',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }
  const handleOpenFieldMapping = async () => {
  if (!result?.document_id) {
    addToast(
      'Save the OCR result before opening Field Mapping.',
      'error',
    )
    return
  }

  if (!connectionId) {
    addToast(
      'A connected NetSuite account is required for Field Mapping.',
      'error',
    )
    return
  }

  try {
    setSaving(true)

    const reviewedData = normalizeEditedData(
      data,
      customFieldTypes,
    )

    const response = await apiClient.post(
      '/ocr/review/save/',
      {
        document_id: result.document_id,
        data: reviewedData,
      },
    )

    const responseData =
      response?.data?.data ??
      response?.data ??
      {}

    const savedResult = {
      ...result,
      document_id:
        responseData?.document_id ||
        result.document_id ||
        null,
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
        reviewedData,
    }

    setData(cloneData(savedResult.data))

    sessionStorage.setItem(
      'ocr_field_mapping_context',
      JSON.stringify({
        connection_id: connectionId,
        record_type: 'vendorBill',
        upload_id:
          savedResult.upload_id || null,
        document_id:
          savedResult.document_id,
        version_id:
          savedResult.version_id || null,
        filename:
          savedResult.filename || null,
        data:
          savedResult.data || {},
        requested_fields:
          savedResult.requested_fields || null,
        source: 'ocr-history',
      }),
    )

    navigate('/app/ocr-test/field-mapping')
  } catch (err) {
    console.error(
      'Failed to save OCR data before Field Mapping:',
      err,
    )

    addToast(
      err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to save OCR changes before Field Mapping.',
      'error',
    )
  } finally {
    setSaving(false)
  }
}


  const handlePost = async () => {
    if (!result?.document_id) {
      addToast(
        'Please save the OCR data before posting it to NetSuite.',
        'error',
      )
      return
    }

    try {
      setPosting(true)

      if (onPost) {
        await onPost(result.document_id, connectionId)
        addToast('Vendor Bill posted to NetSuite.', 'success')
        return
      }

      const response = await apiClient.post(
        '/netsuite/ocr/post-vendor-bill/',
        {
          document_id: result.document_id,
        },
      )

      const responseData =
        response?.data?.data ?? response?.data ?? {}

      const recordId = responseData?.netsuite_record_id

      addToast(
        recordId
          ? `Vendor Bill created in NetSuite. Record ID: ${recordId}`
          : 'Vendor Bill created in NetSuite.',
        'success',
      )
    } catch (err) {
      console.error('Failed to post Vendor Bill to NetSuite:', err)

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
  

  const handleValidate = async () => {
    if (!onValidate || !result?.document_id) return
    try {
      await onValidate(result.document_id)
      addToast('Validation completed.', 'success')
    } catch (err) {
      console.error('Validation failed:', err)
      addToast(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Validation failed.',
        'error',
      )
    }
  }

  if (!result) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-center">
        <div>
          <p className="text-sm font-medium text-[var(--color-ink)]">
            No OCR result selected.
          </p>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            Upload or open an OCR history record to review its data.
          </p>
        </div>
      </div>
    )
  }

  if (result.status === 'FAILED') {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {result.error || 'OCR extraction failed for this file.'}
      </div>
    )
  }

  return (
    <div className="relative flex flex-col gap-5">
      <Toast toasts={toasts} removeToast={removeToast} />

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
                  <tr key={`${result.upload_id || result.document_id}-${index}`}>
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

      <div
        className={`flex flex-wrap items-center justify-end gap-2 border-t border-[var(--color-border)] pt-4 ${
          compact ? '' : 'sticky bottom-0 bg-[var(--color-surface)]'
        }`}
      >
        <Button
          type="button"
          intent="secondary"
          onClick={() => {
            setViewMode('fields')
            setEditing(true)
          }}
          disabled={editing || saving}
        >
          Edit
        </Button>

        <Button
          type="button"
          intent="primary"
          onClick={handleSave}
          disabled={
            saving ||
            (!editing && Boolean(result?.document_id))
          }
          isLoading={saving}
        >
          Save
        </Button>
        {result?.document_id && (
    <Button
      type="button"
      intent="secondary"
      onClick={handleOpenFieldMapping}
      disabled={
        saving ||
        posting ||
        !connectionId
      }
    >
      Map Fields with NetSuite
    </Button>
  )}
      </div>
    </div>
  )
}