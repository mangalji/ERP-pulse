import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import { netsuiteApi } from '../../services/netsuite.js'

const CONTEXT_KEY = 'ocr_field_mapping_context'

const STANDARD_LABELS = {
  invoice_id: 'Invoice ID',
  invoice_number: 'Invoice Number',
  invoice_date: 'Invoice Date',
  due_date: 'Due Date',
  vendor_name: 'Vendor Name',
  customer_name: 'Customer Name',
  subsidiary: 'Subsidiary',
  currency: 'Currency',
  subtotal: 'Subtotal',
  tax_amount: 'Tax Amount',
  tax_rate: 'Tax Rate',
  total_amount: 'Total Amount',
  payment_terms: 'Payment Terms',
  description: 'Description',
  quantity: 'Quantity',
  unit_price: 'Unit Price',
  amount: 'Amount',
}

function normalize(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
}

function getApplicationFields(context) {
  const requested = context?.requested_fields
  const data = context?.data

  const standardKeys = Array.isArray(requested?.standard_fields)
    ? requested.standard_fields
    : []

  const customFields = Array.isArray(requested?.custom_fields)
    ? requested.custom_fields
    : []

  const headerFields = standardKeys.map((key) => ({
    key,
    label: STANDARD_LABELS[key] || key,
    scope: 'body',
    type: 'text',
  }))

  const custom = customFields.map((field) => ({
    key: field.id || field.key,
    label: field.label || field.id || field.key,
    description: field.description || '',
    scope:
      field.scope === 'line'
        ? 'line'
        : field.scope === 'sublist'
          ? 'line'
          : 'body',
    type: field.type || field.data_type || 'text',
  }))

  const fallbackKeys =
    standardKeys.length || custom.length
      ? []
      : Object.keys(data || {}).filter(
          (key) => key !== 'line_items' && key !== 'custom_fields',
        )

  const fallback = fallbackKeys.map((key) => ({
    key,
    label: STANDARD_LABELS[key] || key,
    scope: 'body',
    type: typeof data?.[key] === 'number' ? 'number' : 'text',
  }))

  const fields = [...headerFields, ...custom, ...fallback]
  const deduped = new Map()

  fields.forEach((field) => {
    if (field.key) {
      deduped.set(field.key, field)
    }
  })

  const lineItemFields = new Set()

  if (Array.isArray(requested?.line_item_fields)) {
    requested.line_item_fields.forEach((field) => {
      if (typeof field === 'string') lineItemFields.add(field)
      else if (field?.key) lineItemFields.add(field.key)
      else if (field?.id) lineItemFields.add(field.id)
    })
  }

  const lineItems = Array.isArray(data?.line_items) ? data.line_items : []
  if (lineItems.length > 0) {
    Object.keys(lineItems[0] || {}).forEach((key) => lineItemFields.add(key))
  }

  lineItemFields.forEach((key) => {
    if (!key) return
    deduped.set(key, {
      key,
      label: STANDARD_LABELS[key] || key,
      scope: 'line',
      type:
        typeof lineItems?.[0]?.[key] === 'number'
          ? 'number'
          : 'text',
    })
  })

  return [...deduped.values()]
}

function normalizeCatalogue(payload) {
  const raw = payload?.data ?? payload ?? {}

  const fieldContainer = raw?.fields
  const nestedFields =
    fieldContainer &&
    !Array.isArray(fieldContainer)
      ? [
          ...(Array.isArray(fieldContainer.body)
            ? fieldContainer.body
            : []),
          ...(Array.isArray(fieldContainer.column)
            ? fieldContainer.column
            : []),
        ]
      : []

  const candidates =
    nestedFields.length > 0
      ? nestedFields
      : Array.isArray(fieldContainer)
        ? fieldContainer
        : raw?.results ??
          raw?.items ??
          raw?.body_fields ??
          []

  const customFields = Array.isArray(raw?.custom_fields)
    ? raw.custom_fields
    : []

  const source = [...candidates, ...customFields]

  const normalized = []

  source.forEach((field) => {
    if (!field) return

    const id =
      field.id ||
      field.field_id ||
      field.internal_id ||
      field.script_id ||
      field.scriptId

    if (!id) return

    normalized.push({
      id: String(id),
      label:
        field.label ||
        field.display_label ||
        field.name ||
        String(id),
      type:
        field.type ||
        field.field_type ||
        field.datatype ||
        'text',
      scope:
        field.scope ||
        field.level ||
        (field.sublist_id || field.sublist ? 'line' : 'body'),
      reference_type:
        field.reference_type ||
        field.referenceRecordType ||
        null,
      custom:
        Boolean(field.custom || field.is_custom),
    })
  })

  return normalized
}

function suggestTarget(applicationField, catalogue) {
  if (!catalogue.length) return null

  const source = normalize(applicationField.key)
  const sourceLabel = normalize(applicationField.label)

  const scored = catalogue.map((field) => {
    const target = normalize(field.id)
    const targetLabel = normalize(field.label)

    let score = 0

    if (source === target || sourceLabel === targetLabel) {
      score += 100
    }

    if (source && target.includes(source)) score += 35
    if (source && source.includes(target)) score += 25

    const sourceWords = new Set(
      `${source} ${sourceLabel}`.split(' ').filter(Boolean),
    )
    const targetWords = new Set(
      `${target} ${targetLabel}`.split(' ').filter(Boolean),
    )

    const overlap = [...sourceWords].filter((word) =>
      targetWords.has(word),
    ).length

    score += overlap * 10

    if (
      applicationField.scope === 'line' &&
      String(field.scope).toLowerCase() === 'line'
    ) {
      score += 20
    }

    if (
      applicationField.scope !== 'line' &&
      String(field.scope).toLowerCase() !== 'line'
    ) {
      score += 20
    }

    return { field, score }
  })

  scored.sort((a, b) => b.score - a.score)

  return scored[0]?.field || null
}

export default function OcrFieldMappingPage() {
  const navigate = useNavigate()

  const [context, setContext] = useState(null)
  const [catalogue, setCatalogue] = useState([])
  const [mappings, setMappings] = useState([])
  const [loadingContext, setLoadingContext] = useState(true)
  const [catalogueLoading, setCatalogueLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [mapping, setMapping] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [mapAttempt, setMapAttempt] = useState(0)

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(CONTEXT_KEY)
      if (!raw) {
        setError(
          'No OCR result is available for Field Mapping. Return to OCR and select a completed result.',
        )
        return
      }

      setContext(JSON.parse(raw))
    } catch (err) {
      console.error('Failed to load OCR mapping context:', err)
      setError('The OCR mapping context is invalid or expired.')
    } finally {
      setLoadingContext(false)
    }
  }, [])

  const applicationFields = useMemo(
    () => getApplicationFields(context),
    [context],
  )

  const catalogueOptionsByScope = useMemo(() => {
    const body = catalogue.filter(
      (field) =>
        String(field.scope).toLowerCase() !== 'line',
    )
    const line = catalogue.filter(
      (field) =>
        String(field.scope).toLowerCase() === 'line',
    )

    return { body, line }
  }, [catalogue])

  const loadCatalogueAndSavedMappings = useCallback(async () => {
    if (!context?.connection_id) {
      setError(
        'No NetSuite connection is available for this OCR result.',
      )
      return
    }

    try {
      setCatalogueLoading(true)
      setError('')

      const [catalogueResponse, savedResponse] =
        await Promise.all([
          netsuiteApi.getFieldCatalogue(
            context.connection_id,
            'vendorBill',
          ),
          netsuiteApi.listFieldMappings(
            context.connection_id,
            'vendorBill',
          ),
        ])

      const actualFields = normalizeCatalogue(catalogueResponse)
      const savedPayload =
        savedResponse?.data ?? savedResponse ?? {}
      const saved = Array.isArray(savedPayload)
        ? savedPayload
        : savedPayload?.results ??
          savedPayload?.mappings ??
          []

      setCatalogue(actualFields)

      const savedBySource = new Map(
        saved
          .filter((item) => item?.source_field_key)
          .map((item) => [
            item.source_field_key,
            {
              target_field_id:
                item.target_field_id ||
                item.target_field ||
                null,
              target_field_label:
                item.target_field_label ||
                item.target_field_name ||
                null,
              status:
                item.mapping_status ||
                item.status ||
                'MAPPED',
              confidence:
                item.confidence ?? null,
            },
          ]),
      )

      setMappings(
        applicationFields.map((field) => {
          const savedMapping = savedBySource.get(field.key)
          const target =
            savedMapping?.target_field_id
              ? actualFields.find(
                  (candidate) =>
                    candidate.id ===
                    String(savedMapping.target_field_id),
                )
              : null

          return {
            source_field_key: field.key,
            source_label: field.label,
            source_scope: field.scope,
            target_field_id:
              target?.id || savedMapping?.target_field_id || null,
            target_field_label:
              target?.label ||
              savedMapping?.target_field_label ||
              null,
            status:
              savedMapping?.status ||
              (target ? 'MAPPED' : 'UNRESOLVED'),
            confidence:
              savedMapping?.confidence ?? null,
          }
        }),
      )
    } catch (err) {
      console.error('Failed to load NetSuite mapping metadata:', err)
      const message = err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to load NetSuite Vendor Bill fields.'
        setError(message)
        setNotice('')
      setCatalogue([])
      setMappings(
        applicationFields.map((field) => ({
          source_field_key: field.key,
          source_label: field.label,
          source_scope: field.scope,
          target_field_id: null,
          target_field_label: null,
          status: 'UNRESOLVED',
          confidence: null,
        })),
      )
      throw err
    } finally {
      setCatalogueLoading(false)
    }
  }, [context, applicationFields])

  const handleMapFields = async () => {
    if (!context?.connection_id) {
      setError(
        'A connected NetSuite account is required before fields can be mapped.',
      )
      return
    }

    try {
      setMapping(true)
      setNotice('')
      setError('')

      await loadCatalogueAndSavedMappings()

      setMapAttempt((current) => Math.min(2, current + 1))

      setNotice(
        'NetSuite Vendor Bill fields loaded. Review the suggested mappings below.',
      )
    } catch (err) {
      console.error('Field mapping load failed:', err)

      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Field mapping failed.',
      )
    } finally {
      setMapping(false)
    }
  }

  useEffect(() => {
    if (!catalogue.length || !applicationFields.length) {
      return
    }

    setMappings((current) => {
      const existingBySource = new Map(
        current.map((item) => [
          item.source_field_key,
          item,
        ]),
      )

      let changed = false

      const next = applicationFields.map((field) => {
        const existing = existingBySource.get(field.key)

        if (existing?.target_field_id) {
          return existing
        }

        const options =
          field.scope === 'line'
            ? catalogueOptionsByScope.line
            : catalogueOptionsByScope.body

        const suggestion = suggestTarget(field, options)

        const nextItem = {
          source_field_key: field.key,
          source_label: field.label,
          source_scope: field.scope,
          target_field_id: suggestion?.id || null,
          target_field_label: suggestion?.label || null,
          status: suggestion ? 'MAPPED' : 'UNRESOLVED',
          confidence: suggestion ? 0.75 : 0,
        }

        if (
          !existing ||
          existing.target_field_id !== nextItem.target_field_id ||
          existing.status !== nextItem.status
        ) {
          changed = true
        }

        return existing || nextItem
      })

      if (
        next.length !== current.length ||
        !next.every(
          (item, index) =>
            item?.source_field_key ===
            current?.[index]?.source_field_key,
        )
      ) {
        changed = true
      }

      return changed ? next : current
    })
  }, [
    catalogue,
    applicationFields,
    catalogueOptionsByScope,
  ])

  const updateMapping = (sourceKey, targetId) => {
    const allOptions = catalogue
    const target = allOptions.find(
      (field) => field.id === targetId,
    )

    setMappings((current) =>
      current.map((item) =>
        item.source_field_key === sourceKey
          ? {
              ...item,
              target_field_id: target?.id || null,
              target_field_label: target?.label || null,
              status: target ? 'MAPPED' : 'UNRESOLVED',
              confidence: target ? 1 : 0,
            }
          : item,
      ),
    )
    setNotice('')
  }

  const handleSaveMapping = async () => {
    if (!context?.connection_id) {
      setError('A NetSuite connection is required to save mapping.')
      return
    }

    const unresolved = mappings.filter(
      (item) => !item.target_field_id,
    )

    if (unresolved.length) {
      setError(
        `Complete the mapping for ${unresolved.length} application field(s) before continuing.`,
      )
      return
    }

    try {
      setSaving(true)
      setError('')

      await netsuiteApi.saveFieldMappings(
        context.connection_id,
        'vendorBill',
        mappings.map((item) => ({
          source_field_key: item.source_field_key,
          target_field_id: item.target_field_id,
          mapping_status: item.status || 'MAPPED',
          confidence: item.confidence,
        })),
      )

      setNotice('Field mapping saved successfully.')
    } catch (err) {
      console.error('Failed to save field mapping:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to save field mapping.',
      )
    } finally {
      setSaving(false)
    }
  }

  const handleContinue = () => {
    const unresolved = mappings.filter(
      (item) => !item.target_field_id,
    )

    if (unresolved.length) {
      setError(
        `Resolve all ${unresolved.length} unmapped field(s) before continuing to validation.`,
      )
      return
    }

    sessionStorage.setItem(
      CONTEXT_KEY,
      JSON.stringify({
        ...context,
        mappings,
        mapping_completed: true,
      }),
    )

    setNotice(
      'Mapping confirmed. The next step will be NetSuite Vendor/Item validation.',
    )
  }

  if (loadingContext) {
    return (
      <ClientLayout
        title="Field Mapping"
        breadcrumb="OCR / Field Mapping"
      >
        <div className="mx-auto w-full max-w-7xl">
          <Card className="p-6 text-sm text-[var(--color-muted)]">
            Loading field mapping...
          </Card>
        </div>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout
      title="Field Mapping"
      breadcrumb="OCR / Field Mapping"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
              Field Mapping
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Map the current OCR extraction fields to the connected NetSuite Vendor Bill fields.
            </p>
            {context?.filename && (
              <p className="mt-2 text-xs font-medium text-[var(--color-muted)]">
                File: {context.filename}
              </p>
            )}
          </div>

          <Button
            type="button"
            intent="secondary"
            onClick={() => navigate('/app/ocr-test')}
          >
            ← Back to OCR
          </Button>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {notice && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        )}

        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-ink)]">
                AI-assisted Mapping
              </h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Fetch the actual Vendor Bill fields from this NetSuite connection, then preselect the best match for every application field.
              </p>
            </div>

            <div className="flex items-center gap-2">
              {mapAttempt > 0 && (
                <span className="rounded-full bg-[var(--color-canvas)] px-3 py-1 text-xs font-medium text-[var(--color-muted)]">
                  Mapping attempt {mapAttempt} / 2
                </span>
              )}

              <Button
                type="button"
                onClick={handleMapFields}
                disabled={
                  mapping ||
                  catalogueLoading ||
                  !context?.connection_id ||
                  mapAttempt >= 2
                }
                isLoading={mapping || catalogueLoading}
              >
                {mapAttempt === 0
                  ? 'Map Fields'
                  : 'Run Mapping Again'}
              </Button>
            </div>
          </div>

          {!context?.connection_id && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              No NetSuite connection is available for this OCR result.
            </div>
          )}

          {catalogueLoading && (
            <div className="mt-5 rounded-lg border border-[var(--color-border)] p-5 text-sm text-[var(--color-muted)]">
              Fetching Vendor Bill fields from the connected NetSuite account...
            </div>
          )}

          {!catalogueLoading && catalogue.length === 0 && mapAttempt === 0 && (
            <div className="mt-5 rounded-lg border border-dashed border-[var(--color-border)] p-6 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                Mapping table is not loaded yet
              </p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Click “Map Fields” to fetch the connected NetSuite field catalogue.
              </p>
            </div>
          )}

          {!catalogueLoading && mappings.length > 0 && (
            <div className="mt-6 overflow-hidden rounded-xl border border-[var(--color-border)]">
              <div className="grid grid-cols-[1fr_1fr] border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
                <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  Application Field
                </div>
                <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  NetSuite Vendor Bill Field
                </div>
              </div>

              <div className="divide-y divide-[var(--color-border)]">
                {mappings.map((item) => {
                  const options =
                    item.source_scope === 'line'
                      ? catalogueOptionsByScope.line
                      : catalogueOptionsByScope.body

                  return (
                    <div
                      key={item.source_field_key}
                      className="grid grid-cols-1 gap-3 px-4 py-4 md:grid-cols-[1fr_1fr] md:items-center"
                    >
                      <div className="min-w-0">
                        <p className="break-all text-sm font-semibold text-[var(--color-ink)]">
                          {item.source_label}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                          {item.source_field_key} ·{' '}
                          {item.source_scope === 'line'
                            ? 'Line Item'
                            : 'Body'}
                        </p>
                      </div>

                      <div>
                        <select
                          value={item.target_field_id || ''}
                          onChange={(event) =>
                            updateMapping(
                              item.source_field_key,
                              event.target.value,
                            )
                          }
                          className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                        >
                          <option value="">
                            Select NetSuite field
                          </option>

                          {options.map((field) => (
                            <option key={field.id} value={field.id}>
                              {field.label} ({field.id})
                            </option>
                          ))}
                        </select>

                        <div className="mt-1 flex items-center justify-between gap-3">
                          <span
                            className={`text-xs font-medium ${
                              item.status === 'MAPPED'
                                ? 'text-emerald-600'
                                : 'text-amber-700'
                            }`}
                          >
                            {item.status === 'MAPPED'
                              ? 'AI suggestion / mapped'
                              : 'Unresolved'}
                          </span>

                          {item.confidence !== null &&
                            item.confidence !== undefined && (
                              <span className="text-[11px] text-[var(--color-muted)]">
                                {Math.round(
                                  Number(item.confidence) * 100,
                                )}
                                % confidence
                              </span>
                            )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {mappings.length > 0 && (
            <div className="mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-[var(--color-border)] pt-5">
              <Button
                type="button"
                intent="secondary"
                onClick={handleSaveMapping}
                disabled={saving || mapping}
                isLoading={saving}
              >
                Save Mapping
              </Button>

              <Button
                type="button"
                onClick={handleContinue}
                disabled={
                  saving ||
                  mapping ||
                  !mappings.length ||
                  mappings.some(
                    (item) => !item.target_field_id,
                  )
                }
              >
                Continue to Validation →
              </Button>
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}