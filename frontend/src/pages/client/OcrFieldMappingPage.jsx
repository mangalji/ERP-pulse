import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import apiClient from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import { aiIntegrationApi } from '../../services/aiIntegration.js'

const CONTEXT_KEY = 'ocr_field_mapping_context'

const USER_FRIENDLY_MESSAGES = {
  loadContext:
    'We couldn’t load this result. Please return to OCR and open it again.',
  loadFields:
    'We couldn’t load the fields needed for this step. Please try again.',
  mapFields:
    'We couldn’t prepare the fields for mapping. Please try again.',
  refreshFields:
    'We couldn’t refresh the fields right now. Please try again.',
  saveMapping:
    'We couldn’t save the field mapping. Please review it and try again.',
  validate:
    'We couldn’t complete the check right now. Please try again.',
  batchValidate:
    'We couldn’t complete the check for the selected documents. Please try again.',
  post:
    'We couldn’t create the Vendor Bill right now. Please try again.',
  batchPost:
    'We couldn’t finish processing the selected documents. Please try again.',
  missingDocument:
    'This result is not ready yet. Please save it and try again.',
  missingDocuments:
    'No documents are available for this check. Please return to OCR and try again.',
  missingConnection:
    'Please connect your NetSuite account before continuing.',
  invalidMode:
    'We couldn’t determine how to process these documents. Please return to OCR and try again.',
  generic:
    'Something went wrong. Please try again.',
}

function getValidationErrorMessage() {
  return 'We found a problem with this document. Please review the guidance below.'
}

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

function getErrorReference(validationId, errorIndex) {
  return `${validationId}:${errorIndex}`
}

function ValidationErrorDisplay({
  errorItem,
  diagnostic,
  diagnosing,
  diagnosticError,
}) {
  if (!errorItem || typeof errorItem !== 'object') {
    return (
      <p className="text-sm text-red-700">
        {getValidationErrorMessage()}
      </p>
    )
  }

  const detailFields = [
    ['Item', errorItem.item_name || errorItem.extracted_name],
    ['Item Subsidiary', errorItem.item_subsidiary],
    ['Vendor Bill Subsidiary', errorItem.transaction_subsidiary],
    [
      'Affected Lines',
      Array.isArray(errorItem.affected_lines)
        ? errorItem.affected_lines.join(', ')
        : '',
    ],
  ].filter(([, value]) => value !== undefined && value !== null && value !== '')

  return (
    <div className="rounded-lg border border-red-300 bg-white p-4 text-sm text-red-800">
      <p className="font-semibold">
        Needs your attention
      </p>

      <p className="mt-2 text-xs leading-5 text-red-700">
        {diagnostic?.what_happened || getValidationErrorMessage()}
      </p>

      {detailFields.length > 0 && (
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
          {detailFields.map(([label, value]) => (
            <div key={label}>
              <span className="font-semibold">{label}:</span>{' '}
              {value}
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-800">
            Resolution Guidance
          </p>
          {diagnosing && (
            <span className="text-xs text-slate-500">
              Analyzing…
            </span>
          )}
        </div>

        {diagnostic && (
          <div className="mt-3 space-y-4 text-xs text-slate-700">
            {diagnostic.what_happened && (
              <div>
                <p className="font-semibold text-slate-900">
                  What happened
                </p>
                <p className="mt-1 leading-5">
                  {diagnostic.what_happened}
                </p>
              </div>
            )}

            {diagnostic.likely_reasons?.length > 0 && (
              <div>
                <p className="font-semibold text-slate-900">
                  Possible reasons
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {diagnostic.likely_reasons.map((reason, index) => (
                    <li key={`reason-${index}`}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {diagnostic.possible_solutions?.length > 0 && (
              <div>
                <p className="font-semibold text-slate-900">
                  Possible solutions
                </p>

                <div className="mt-2 space-y-2">
                  {diagnostic.possible_solutions.map((solution, index) => (
                    <div
                      key={`solution-${index}`}
                      className={
                        solution.recommended
                          ? 'rounded-md border border-emerald-300 bg-emerald-50 px-3 py-3'
                          : 'rounded-md border border-slate-200 bg-white px-3 py-3'
                      }
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-900">
                          {index + 1}. {solution.title}
                        </span>
                        {solution.recommended && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                            Recommended
                          </span>
                        )}
                      </div>

                      {solution.reason && (
                        <p className="mt-1 leading-5">
                          {solution.reason}
                        </p>
                      )}

                      {solution.steps?.length > 0 && (
                        <ol className="mt-2 list-decimal space-y-1 pl-5">
                          {solution.steps.map((step, stepIndex) => (
                            <li key={`step-${stepIndex}`}>{step}</li>
                          ))}
                        </ol>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {diagnostic.additional_checks?.length > 0 && (
              <div>
                <p className="font-semibold text-slate-900">
                  Check these details if the cause is still unclear
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {diagnostic.additional_checks.map((check, index) => (
                    <li key={`check-${index}`}>{check}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!diagnostic && diagnosing && (
          <p className="mt-2 text-xs text-slate-600">
            Reviewing the NetSuite validation details…
          </p>
        )}

        {!diagnostic && !diagnosing && diagnosticError && (
          <p className="mt-2 text-xs text-slate-600">
            {diagnosticError}
          </p>
        )}
      </div>
    </div>
  )
}

function getApplicationFields(context) {
  const requested = context?.requested_fields
  const data = context?.data

  const standardKeys = Array.isArray(requested?.standard_fields) ? requested.standard_fields : []

  const customFields = Array.isArray(requested?.custom_fields) ? requested.custom_fields : []

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
    // Do NOT overwrite a field that was already explicitly defined as a
    // header/custom field (e.g. requested.standard_fields). Line items
    // often reuse common key names like "description", and letting the
    // auto-detected line-item key silently flip an explicit header
    // field's scope to 'line' causes a header-mapped selection to be
    // saved with the wrong scope and get rejected by the backend.
    if (deduped.has(key)) return
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
        : raw?.results ||
          raw?.items ||
          raw?.body_fields ||
          []

  const customFields = Array.isArray(
    raw?.custom_fields,
  )
    ? raw.custom_fields
    : []

  const source = [
    ...candidates,
    ...customFields,
  ]

  const deduped = new Map()

  source.forEach((field) => {
    if (!field) return

    const id =
      field.id ||
      field.field_id ||
      field.internal_id ||
      field.script_id ||
      field.scriptId

    if (!id) return

    const rawScope = String(
      field.scope ||
      field.level ||
      (
        field.sublist_id ||
        field.sublist
          ? 'line'
          : 'body'
      ),
    ).toLowerCase()

    const scope = [
      'line',
      'column',
      'sublist',
    ].includes(rawScope)
      ? 'line'
      : 'body'

    const normalized = {
      id: String(id),

      label:
        field.label ||
        field.display_label ||
        field.name ||
        String(id),

      type:
        field.datatype ||
        field.type ||
        field.field_type ||
        'text',

      scope,

      reference_type:
        field.reference_type ||
        field.referenceRecordType ||
        null,

      is_required: Boolean(
        field.is_required,
      ),

      is_custom: Boolean(
        field.is_custom ??
        field.custom,
      ),

      baseline: Boolean(
        field.baseline,
      ),

      description:
        field.description || '',
    }

    // Same ID may legitimately exist once in body
    // and once in line scope.
    const key = `${normalized.id}:${scope}`

    deduped.set(key, normalized)
  })

  return [...deduped.values()]
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
  const [refreshingFields, setRefreshingFields] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [posting, setPosting] = useState(false)
  const [postingResult, setPostingResult] = useState(null)
  const [aiDiagnostics, setAiDiagnostics] = useState([])
  const [diagnosing, setDiagnosing] = useState(false)
  const [diagnosticError, setDiagnosticError] = useState('')

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(CONTEXT_KEY)
      if (!raw) {
        setError(USER_FRIENDLY_MESSAGES.loadContext)
        return
      }

      setContext(JSON.parse(raw))
    } catch (err) {
      console.error('Failed to load OCR mapping context:', err)
      setError(USER_FRIENDLY_MESSAGES.loadContext)
    } finally {
      setLoadingContext(false)
    }
  }, [])

  const applicationFields = useMemo(
    () => getApplicationFields(context),
    [context],
  )

  const aiDiagnosticsByReference = useMemo(
    () => new Map(
      (aiDiagnostics || []).map((diagnostic) => [
        diagnostic.error_reference,
        diagnostic,
      ]),
    ),
    [aiDiagnostics],
  )

  const documentIds = useMemo(() => {
    if (Array.isArray(context?.document_ids) && context.document_ids.length) {
      return [
        ...new Set(
          context.document_ids
            .filter(Boolean)
            .map(String),
        ),
      ]
    }

    if (Array.isArray(context?.documents) && context.documents.length) {
      return [
        ...new Set(
          context.documents
            .map((item) => item?.document_id)
            .filter(Boolean)
            .map(String),
        ),
      ]
    }

    if (context?.document_id) {
      return [String(context.document_id)]
    }

    if (context?.document?.id) {
      return [String(context.document.id)]
    }

    return []
  }, [context])

  const processingMode = (() => {
    const explicitMode = String(
      context?.processing_mode || '',
    ).toUpperCase()

    if (explicitMode === 'SINGLE' || explicitMode === 'MULTIPLE') {
      return explicitMode
    }

    const documentCount =
      Array.isArray(context?.document_ids)
        ? context.document_ids.filter(Boolean).length
        : Array.isArray(context?.documents)
          ? context.documents.filter(
              (item) => item?.document_id,
            ).length
          : context?.document_id
            ? 1
            : 0

    return documentCount > 1 ? 'MULTIPLE' : 'SINGLE'
  })()

  const documentId =  
    documentIds.length === 1
      ? documentIds[0]
      : null

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

  const loadCatalogueAndSavedMappings = useCallback(
  async ({
    forceRefresh = false,
    runAiMapping = false,
  } = {}) => {
    if (!context?.connection_id) {
      const message =
        'No NetSuite connection is available for this OCR result.'

      setError(message)
      throw new Error(message)
    }

    setCatalogueLoading(!forceRefresh)
    setRefreshingFields(forceRefresh)
    setError('')
    setNotice('')

    try {
      const [
        catalogueResponse,
        savedResponse,
      ] = await Promise.all([
        netsuiteApi.getFieldCatalogue(
          context.connection_id,
          'vendorBill',
          forceRefresh,
        ),

        netsuiteApi.listFieldMappings(
          context.connection_id,
          'vendorBill',
        ),
      ])

      const actualFields =
        normalizeCatalogue(
          catalogueResponse,
        )

      const savedPayload =
        savedResponse?.data ??
        savedResponse ??
        {}

      const saved = Array.isArray(
        savedPayload,
      )
        ? savedPayload
        : (
            savedPayload?.results ||
            savedPayload?.mappings ||
            []
          )

      setCatalogue(actualFields)

      const savedBySource = new Map(
        saved
          .filter(
            (item) =>
              item?.source_field_key,
          )
          .map((item) => [
            item.source_field_key,
            item,
          ]),
      )

      const initialMappings =
        applicationFields.map((field) => {
          const savedMapping =
            savedBySource.get(
              field.key,
            )

          const expectedScope =
            field.scope === 'line'
              ? 'line'
              : 'body'

          const savedTargetId = String(
            savedMapping?.target_field_id || '',
          )

          // Prefer a strict match (same id AND expected scope). If the
          // saved target can't be found with that scope (stale data,
          // catalogue changed, connection refreshed, etc.), fall back to
          // matching the id in ANY scope so we can recover its real
          // scope instead of guessing. Never keep a target_field_id
          // whose scope we can't actually verify — a null/unknown scope
          // silently defaults to "body" on the backend and produces a
          // false "line field mapped to body field" error even when the
          // source is genuinely unresolved or was saved correctly.
          const target =
            (savedTargetId &&
              actualFields.find(
                (candidate) =>
                  candidate.id === savedTargetId &&
                  candidate.scope === expectedScope,
              )) ||
            (savedTargetId &&
              actualFields.find(
                (candidate) => candidate.id === savedTargetId,
              )) ||
            null

          return {
            source_field_key: field.key,
            source_field_label: field.label,
            source_scope: field.scope,
            source_datatype: field.type,

            // Only keep a target_field_id when we found it (with a
            // known, verified scope) in the current catalogue. If it
            // can't be found at all, treat the field as unresolved
            // rather than carrying forward a broken reference.
            target_field_id:
              target?.id || null,

            target_field_label:
              target?.label ||
              (target ? savedMapping?.target_field_label : null) ||
              null,

            target_scope:
              target?.scope || null,

            target_datatype:
              target?.type || null,

            is_required:
              Boolean(
                target?.is_required,
              ),

            is_custom:
              Boolean(
                target?.is_custom,
              ),

            reference_type:
              target?.reference_type ||
              null,

            status:
              target
                ? (
                    savedMapping?.mapping_status ||
                    savedMapping?.status ||
                    'MAPPED'
                  )
                : 'UNRESOLVED',

            confidence:
              savedMapping?.confidence ??
              null,

            candidates:
              [],
          }
        })

      let nextMappings =
        initialMappings

      if (
        runAiMapping &&
        actualFields.length > 0 &&
        applicationFields.length > 0
      ) {
        const aiResponse = await netsuiteApi.suggestFieldMappings(
          context.connection_id,
          'vendorBill',
          applicationFields.map((field) => ({
            key: field.key,
            label: field.label,
            description: field.description || '',
            scope: field.scope === 'line' ? 'line' : 'header',
            datatype: [
              'text',
              'number',
              'date',
              'boolean',
              'currency',
            ].includes(field.type)
              ? field.type
              : 'text',
            is_custom: Boolean(field.is_custom),
          })),
        )

        const aiPayload = aiResponse?.data ?? aiResponse ?? {}
        const aiMappings = Array.isArray(aiPayload)
          ? aiPayload
          : aiPayload?.mappings || aiPayload?.results || []

        const targetsByKey = new Map(
          actualFields.map((field) => [
            `${String(field.id).toLowerCase()}:${field.scope}`,
            field,
          ]),
        )

        nextMappings = initialMappings.map((item) => {
          // A mapping already saved for this source field is authoritative.
          // AI should never silently replace a user's confirmed mapping.
          const savedMapping = savedBySource.get(
            item.source_field_key,
          )
          if (savedMapping?.target_field_id) {
            return item
          }

          const suggestion = aiMappings.find(
            (mapping) =>
              String(
                mapping?.source_field_key ||
                  mapping?.source_key ||
                  mapping?.source_field ||
                  '',
              ) === item.source_field_key,
          )

          if (!suggestion) {
            return item
          }

          const status = String(
            suggestion.status ||
              suggestion.mapping_status ||
              'UNRESOLVED',
          ).toUpperCase()

          let targetId =
            suggestion.target_field_id ||
            suggestion.suggested_target_id ||
            suggestion.target_field ||
            null

          if (
            targetId &&
            typeof targetId === 'object'
          ) {
            targetId =
              targetId.field_id ||
              targetId.id ||
              targetId.internal_id ||
              null
          }

          const nestedTarget =
            suggestion.suggested_target ||
            suggestion.target ||
            null

          if (
            !targetId &&
            nestedTarget &&
            typeof nestedTarget === 'object'
          ) {
            targetId =
              nestedTarget.field_id ||
              nestedTarget.id ||
              nestedTarget.internal_id ||
              null
          }

          const expectedScope =
            item.source_scope === 'line'
              ? 'line'
              : 'body'

          const target = targetId
            ? targetsByKey.get(
                `${String(targetId).toLowerCase()}:${expectedScope}`,
              )
            : null

          if (status !== 'MAPPED' || !target) {
            return {
              ...item,
              target_field_id: null,
              target_field_label: null,
              target_scope: null,
              target_datatype: null,
              is_required: false,
              is_custom: false,
              reference_type: null,
              status:
                status === 'AMBIGUOUS'
                  ? 'AMBIGUOUS'
                  : 'UNRESOLVED',
              confidence:
                suggestion.confidence ?? null,
              candidates:
                suggestion.candidates || [],
              metadata: suggestion.metadata || {},
            }
          }

          return {
            ...item,
            target_field_id: target.id,
            target_field_label: target.label,
            target_scope: target.scope,
            target_datatype: target.type,
            is_required: Boolean(target.is_required),
            is_custom: Boolean(target.is_custom),
            reference_type: target.reference_type || null,
            status: 'MAPPED',
            confidence: suggestion.confidence ?? null,
            candidates: suggestion.candidates || [],
            metadata: suggestion.metadata || {},
          }
        })
      }

      setMappings(nextMappings)
    } catch (err) {
      console.error(
        'Failed to load NetSuite mapping metadata:',
        err,
      )

      setError(USER_FRIENDLY_MESSAGES.loadFields)

      setMappings(
        applicationFields.map(
          (field) => ({
            source_field_key:
              field.key,
            source_field_label:
              field.label,
            source_scope:
              field.scope,
            source_datatype:
              field.type,
            target_field_id: null,
            target_field_label:
              null,
            target_scope: null,
            target_datatype: null,
            is_required: false,
            is_custom: false,
            reference_type: null,
            status: 'UNRESOLVED',
            confidence: null,
            candidates: [],
          }),
        ),
      )

      throw err
    } finally {
      setCatalogueLoading(false)
      setRefreshingFields(false)
    }
  },
  [
    context,
    applicationFields,
  ],
)

  const handleMapFields = async () => {
    if (!context?.connection_id) {
      setError(USER_FRIENDLY_MESSAGES.missingConnection)
      return
    }

    try {
      setMapping(true)

      await loadCatalogueAndSavedMappings({
        forceRefresh: false,
        runAiMapping: true,
      })

      setMapAttempt((current) => Math.min(2, current + 1))

      setNotice(
        'NetSuite Vendor Bill fields loaded. Review the suggested mappings below.',
      )
    } catch (err) {
      console.error('Field mapping load failed:', err)
      setError(USER_FRIENDLY_MESSAGES.mapFields)
      setNotice('')
    } finally {
      setMapping(false)
      setCatalogueLoading(false)
      setRefreshingFields(false)
    }
  }

  const handleRefreshFields = async () => {
  if (!context?.connection_id) {
    setError(USER_FRIENDLY_MESSAGES.missingConnection)
    return
  }

  try {
    await loadCatalogueAndSavedMappings({
      forceRefresh: true,
      runAiMapping: false,
    })

    setNotice(
      'NetSuite Vendor Bill fields were refreshed from the connected account.',
    )
  } catch (err) {
    console.error('NetSuite field refresh failed:', err)
  }
}

  const updateMapping = (
  sourceKey,
  targetId,
) => {
  const source =
    mappings.find(
      (item) =>
        item.source_field_key ===
        sourceKey,
    )

  const target = catalogue.find(
    (field) =>
      field.id === targetId &&
      field.scope ===
        (
          source?.source_scope === 'line'
            ? 'line'
            : 'body'
        ),
  )

  setValidationResult(null)
  setPostingResult(null)

  setMappings((current) =>
    current.map((item) =>
      item.source_field_key ===
      sourceKey
        ? {
            ...item,

            target_field_id:
              target?.id || null,

            target_field_label:
              target?.label || null,

            target_scope:
              target?.scope || null,

            target_datatype:
              target?.type || null,

            is_required:
              Boolean(
                target?.is_required,
              ),

            is_custom:
              Boolean(
                target?.is_custom,
              ),

            reference_type:
              target?.reference_type ||
              null,

            status:
              target
                ? 'MAPPED'
                : 'UNRESOLVED',

            confidence:
              target ? 1 : 0,
          }
        : item,
    ),
  )

  setNotice('')
}


  const buildMappingPayload = useCallback(
    (items) =>
      items.map((item) => ({
        source_field_key: item.source_field_key,
        source_field_label:
          item.source_field_label ||
          item.source_label ||
          item.source_field_key,
        source_scope:
          item.source_scope === 'line'
            ? 'line'
            : 'header',
        source_datatype:
          item.source_datatype ||
          'text',
        target_field_id:
          item.target_field_id || '',
        target_field_label:
          item.target_field_label || '',
        target_scope:
          item.target_scope ||
          (item.source_scope === 'line'
            ? 'column'
            : 'body'),
        target_datatype:
          item.target_datatype ||
          'text',
        is_required: Boolean(
          item.is_required,
        ),
        is_custom: Boolean(
          item.is_custom,
        ),
        reference_type:
          item.reference_type ||
          null,
        mapping_status:
          item.target_field_id
            ? 'MAPPED'
            : 'UNRESOLVED',
        confidence:
          item.confidence ?? null,
        metadata:
          item.metadata || {},
      })),
    [],
  )

  const handleSaveMapping = async () => {
    if (!context?.connection_id) {
      setError(USER_FRIENDLY_MESSAGES.missingConnection)
      return
    }

    if (!mappings.some((item) => item.target_field_id)) {
      setError(
        'Map at least one application field before saving.',
      )
      return
    }

    try {
      setSaving(true)
      setError('')
      setNotice('')
    
      await netsuiteApi.saveFieldMappings(
        context.connection_id,
        'vendorBill',
        buildMappingPayload(mappings),
      )
    
      setNotice(
        'Field mapping saved successfully.',
      )
    
      return true
    } catch (err) {
      console.error(
        'Failed to save field mapping:',
        err,
      )
    
      setError(USER_FRIENDLY_MESSAGES.saveMapping)
    
      return false
    } finally {
      setSaving(false)
    }
  }

const requestNetSuiteDiagnostics = useCallback(
  async (validationIds) => {
    const ids = [
      ...new Set(
        (validationIds || [])
          .filter(Boolean)
          .map(String),
      ),
    ]

    if (!ids.length || !context?.connection_id) {
      setAiDiagnostics([])
      setDiagnosticError('')
      return
    }

    setAiDiagnostics([])
    setDiagnosticError('')
    setDiagnosing(true)

    try {
      const result =
        await aiIntegrationApi.diagnoseNetSuiteValidation({
          validation_ids: ids,
          connection_id: context.connection_id,
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

      setDiagnosticError(
        'We couldn’t prepare the resolution guidance right now. The validation result above is still available. Please try again.',
      )
    } finally {
      setDiagnosing(false)
    }
  },
  [context?.connection_id],
)

const runValidation = async () => {
  if (!context?.connection_id) {
    setError(USER_FRIENDLY_MESSAGES.missingConnection)
    return
  }

  if (
    processingMode === 'SINGLE' &&
    !documentId
  ) {
    setError(USER_FRIENDLY_MESSAGES.missingDocument)
    return
  }

  if (
    processingMode === 'MULTIPLE' &&
    !documentIds.length
  ) {
    setError(USER_FRIENDLY_MESSAGES.missingDocuments)
    return
  }

  try {
    setValidating(true)
    setError('')
    setNotice('')
    setAiDiagnostics([])
    setDiagnosticError('')

    if (processingMode === 'SINGLE') {
      const result =
        await netsuiteApi.validateDocument(
          documentId,
          context.connection_id,
        )

      setValidationResult(result)

      const singleValidationErrors =
        Array.isArray(result?.errors)
          ? result.errors
          : []

      if (singleValidationErrors.length > 0 && result?.validation_id) {
        void requestNetSuiteDiagnostics([
          result.validation_id,
        ])
      } else {
        setAiDiagnostics([])
        setDiagnosticError('')
      }

      sessionStorage.setItem(
        CONTEXT_KEY,
        JSON.stringify({
          ...context,
          mappings,
          mapping_completed: true,
          validation_result: result,
        }),
      )

      if (result?.status === 'VALIDATED') {
        setNotice(
          '✓ NetSuite validation successful. The document is ready to post.',
        )
      } else {
        setNotice(
          'NetSuite validation completed with validation errors. Review the result before posting.',
        )
      }

      return
    }

    if (processingMode === 'MULTIPLE') {
      const queued =
        await netsuiteApi.validateBatchDocuments(
          documentIds,
          context.connection_id,
        )

      const jobId = queued?.job_id

      if (!jobId) {
        throw new Error(
          'NetSuite batch validation did not return a job ID.',
        )
      }

      setNotice(
        `NetSuite batch validation started for ${documentIds.length} document(s).`,
      )

      const maxAttempts = 120
      const pollIntervalMs = 1500

      for (
        let attempt = 0;
        attempt < maxAttempts;
        attempt += 1
      ) {
        const statusResponse =
          await netsuiteApi.getBatchJobStatus(jobId)

        const statusData =
          statusResponse?.data ??
          statusResponse ??
          {}

        const jobStatus = String(
          statusData.status || '',
        ).toUpperCase()

        if (
          jobStatus === 'SUCCESS' ||
          jobStatus === 'FAILURE' ||
          jobStatus === 'REVOKED'
        ) {
          const finalResult = {
            ...statusData,
            job_id: jobId,
          }

          setValidationResult(finalResult)

          const failedValidationIds =
            Array.isArray(finalResult?.results)
              ? finalResult.results
                  .filter(
                    (item) =>
                      Array.isArray(item?.errors) &&
                      item.errors.length > 0 &&
                      item?.validation_id,
                  )
                  .map((item) => item.validation_id)
              : []

          if (failedValidationIds.length > 0) {
            void requestNetSuiteDiagnostics(
              failedValidationIds,
            )
          } else {
            setAiDiagnostics([])
            setDiagnosticError('')
          }

          sessionStorage.setItem(
            CONTEXT_KEY,
            JSON.stringify({
              ...context,
              mappings,
              mapping_completed: true,
              validation_result: finalResult,
            }),
          )

          if (jobStatus === 'SUCCESS') {
            const failedCount =
              Number(statusData.failed || 0)

            if (failedCount === 0) {
              setNotice(
                '✓ All OCR documents were validated successfully against NetSuite.',
              )
            } else {
              setNotice(
                `Batch validation completed with ${failedCount} failed document(s). Review the results.`,
              )
            }
          } else {
            setError(USER_FRIENDLY_MESSAGES.batchValidate)
          }

          return
        }

        await new Promise((resolve) =>
          setTimeout(
            resolve,
            pollIntervalMs,
          ),
        )
      }

      throw new Error(USER_FRIENDLY_MESSAGES.batchValidate)
    }

    setError(
      'Unsupported OCR processing mode.',
    )
  } catch (err) {
    console.error(
      'NetSuite OCR validation failed:',
      err,
    )

    setError(
      processingMode === 'MULTIPLE'
        ? USER_FRIENDLY_MESSAGES.batchValidate
        : USER_FRIENDLY_MESSAGES.validate,
    )
  } finally {
    setValidating(false)
  }
}
const handleContinue = async () => {
  const saved = await handleSaveMapping()

  if (!saved){
    return 
  }

  await runValidation()
}


const handleValidateAgain = async () => {
  await runValidation()
}
const handlePost = async () => {
  if (!context?.connection_id) {
    setError(USER_FRIENDLY_MESSAGES.missingConnection)
    return
  }

  if (processingMode === 'SINGLE') {
    if (validationResult?.status !== 'VALIDATED') {
      setError(
        'The document must be successfully validated before posting.',
      )
      return
    }

    if (!documentId) {
      setError(USER_FRIENDLY_MESSAGES.missingDocument)
      return
    }

    try {
      setPosting(true)
      setError('')
      setNotice('')
      setPostingResult(null)

      const result =
        await netsuiteApi.postOCRVendorBill(
          documentId,
          context.connection_id,
        )

      setPostingResult(result)

      setNotice(
        `✓ Vendor Bill posted successfully to NetSuite. Record ID: ${
          result?.netsuite_record_id || 'created'
        }`,
      )
    } catch (err) {
      console.error(
        'NetSuite Vendor Bill posting failed:',
        err,
      )

      setError(USER_FRIENDLY_MESSAGES.post)
    } finally {
      setPosting(false)
    }

    return
  }

  if (processingMode === 'MULTIPLE') {
    if (
      !Array.isArray(validationResult?.results) ||
      validationResult.results.length === 0
    ) {
      setError(
        'No batch validation results are available for posting.',
      )
      return
    }

    const validatedDocumentIds =
      validationResult.results
        .filter(
          (item) =>
            String(item?.status || '').toUpperCase() ===
            'VALIDATED',
        )
        .map((item) => item?.document_id)
        .filter(Boolean)

    if (!validatedDocumentIds.length) {
      setError(
        'No successfully validated documents are available for posting.',
      )
      return
    }

    try {
      setPosting(true)
      setError('')
      setNotice('')
      setPostingResult(null)

      const queued =
        await netsuiteApi.batchPostDocuments(
          validatedDocumentIds,
          context.connection_id,
        )

      const jobId = queued?.job_id

      if (!jobId) {
        throw new Error(USER_FRIENDLY_MESSAGES.batchPost)
      }

      setNotice(
        `NetSuite batch posting started for ${validatedDocumentIds.length} document(s).`,
      )

      const maxAttempts = 120
      const pollIntervalMs = 1500

      for (
        let attempt = 0;
        attempt < maxAttempts;
        attempt += 1
      ) {
        const statusResponse =
          await netsuiteApi.getBatchJobStatus(jobId)

        const statusData =
          statusResponse?.data ??
          statusResponse ??
          {}

        const jobStatus = String(
          statusData.status || '',
        ).toUpperCase()

        if (
          jobStatus === 'SUCCESS' ||
          jobStatus === 'FAILURE' ||
          jobStatus === 'REVOKED'
        ) {
          const finalResult = {
            ...statusData,
            job_id: jobId,
          }

          setPostingResult(finalResult)

          if (jobStatus === 'SUCCESS') {
            const failedCount =
              Number(statusData.failed || 0)

            if (failedCount === 0) {
              setNotice(
                '✓ All validated OCR documents were posted successfully to NetSuite.',
              )
            } else {
              setNotice(
                `Batch posting completed with ${failedCount} failed document(s). Review the posting results.`,
              )
            }
          } else {
            setError(USER_FRIENDLY_MESSAGES.batchPost)
          }

          return
        }

        await new Promise((resolve) =>
          setTimeout(
            resolve,
            pollIntervalMs,
          ),
        )
      }

      throw new Error(USER_FRIENDLY_MESSAGES.batchPost)
    } catch (err) {
      console.error(
        'NetSuite batch Vendor Bill posting failed:',
        err,
      )

      setError(USER_FRIENDLY_MESSAGES.batchPost)
    } finally {
      setPosting(false)
    }

    return
  }

  setError(USER_FRIENDLY_MESSAGES.invalidMode)
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
    <ClientLayout title="Field Mapping" breadcrumb="OCR / Field Mapping">
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

          <Button type="button" intent="secondary" onClick={() => navigate('/app/ocr')}>
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
        {validationResult && (
  <Card className="p-5 sm:p-6">
    {processingMode === 'MULTIPLE' ? (
      <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-ink)]">
              NetSuite Batch Validation
            </h2>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Validation results for all OCR documents were checked against
              the connected NetSuite account.
            </p>
          </div>

          <span
            className={
              Number(validationResult.failed || 0) === 0 &&
              Number(validationResult.completed || 0) ===
                Number(validationResult.total || 0)
                ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
            }
          >
            {Number(validationResult.failed || 0) === 0 &&
            Number(validationResult.completed || 0) ===
              Number(validationResult.total || 0)
              ? '✓ VALIDATION SUCCESSFUL'
              : '✕ VALIDATION COMPLETED WITH ERRORS'}
          </span>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Total Documents
            </p>
            <p className="mt-1 text-lg font-semibold">
              {validationResult.total || 0}
            </p>
          </div>

          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Completed
            </p>
            <p className="mt-1 text-lg font-semibold">
              {validationResult.completed || 0}
            </p>
          </div>

          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Successful
            </p>
            <p className="mt-1 text-lg font-semibold text-emerald-700">
              {validationResult.succeeded || 0}
            </p>
          </div>

          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Failed
            </p>
            <p className="mt-1 text-lg font-semibold text-red-700">
              {validationResult.failed || 0}
            </p>
          </div>
        </div>

        {Array.isArray(validationResult.results) &&
          validationResult.results.length > 0 && (
            <div className="mt-5 rounded-lg border">
              <div className="border-b bg-[var(--color-canvas)] px-4 py-3">
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  Document Results
                </p>
              </div>

              <div className="divide-y">
                {validationResult.results.map((item, index) => {
                  const status = String(
                    item?.status || '',
                  ).toUpperCase()

                  const isSuccess =
                    status === 'VALIDATED'

                  const errors = Array.isArray(item?.errors)
                    ? item.errors
                    : []

                  return (
                    <div
                      key={`${item?.document_id || 'document'}-${index}`}
                      className="px-4 py-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                            Document ID: {item?.document_id || 'Unknown'}
                          </p>

                          {item?.validation_id && (
                            <p className="mt-1 text-xs text-[var(--color-muted)]">
                              Validation ID: {item.validation_id}
                            </p>
                          )}
                        </div>

                        <span
                          className={
                            isSuccess
                              ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                              : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
                          }
                        >
                          {isSuccess
                            ? '✓ VALIDATED'
                            : '✕ VALIDATION FAILED'}
                        </span>
                      </div>

                      {(item?.error || errors.length > 0) && (
                        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
                          <p className="text-xs font-semibold text-red-800">
                            Validation Errors
                          </p>

                          <div className="mt-1 space-y-1">
                            {item?.error && errors.length === 0 && (
                              <p className="text-sm text-red-700">
                                {USER_FRIENDLY_MESSAGES.batchValidate}
                              </p>
                            )}

                            {errors.map((errorItem, errorIndex) => {
                              const errorReference =
                                getErrorReference(
                                  item.validation_id,
                                  errorIndex,
                                )
                              const diagnostic =
                                aiDiagnosticsByReference.get(
                                  errorReference,
                                )

                              return (
                                <ValidationErrorDisplay
                                  key={`${errorItem?.type || 'error'}-${errorIndex}`}
                                  errorItem={errorItem}
                                  diagnostic={diagnostic}
                                  diagnosing={diagnosing}
                                  diagnosticError={diagnosticError}
                                />
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
  {(Number(validationResult.failed || 0) > 0 ||
    validationResult.status === 'FAILURE') && (
    <Button
      type="button"
      intent="secondary"
      onClick={handleValidateAgain}
      disabled={validating || saving || posting || diagnosing}
      isLoading={validating}
    >
      Validate Again
    </Button>
  )}

  {validationResult.status === 'SUCCESS' &&
    Array.isArray(validationResult.results) &&
    validationResult.results.some(
      (item) =>
        String(item?.status || '').toUpperCase() ===
        'VALIDATED',
    ) && (
      <Button
        type="button"
        onClick={handlePost}
        disabled={
          posting ||
          validating ||
          (
            postingResult?.status === 'SUCCESS' &&
            Number(postingResult?.failed || 0) === 0
          )
        }
        isLoading={posting}
      >
        {postingResult?.status === 'SUCCESS' &&
        Number(postingResult?.failed || 0) === 0
          ? 'Posted to NetSuite'
          : 'Post to NetSuite'}
      </Button>
    )}
</div>
{postingResult &&
  Array.isArray(postingResult.results) && (
    <div className="mt-4 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--color-ink)]">
            NetSuite Batch Posting
          </p>

          <p className="mt-1 text-xs text-[var(--color-muted)]">
            {postingResult.succeeded || 0} successful ·{' '}
            {postingResult.failed || 0} failed ·{' '}
            {postingResult.total || 0} total
          </p>
        </div>

        <span
          className={
            postingResult.status === 'SUCCESS' &&
            Number(postingResult.failed || 0) === 0
              ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
              : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
          }
        >
          {postingResult.status === 'SUCCESS' &&
          Number(postingResult.failed || 0) === 0
            ? '✓ POSTING SUCCESSFUL'
            : '✕ POSTING COMPLETED WITH ERRORS'}
        </span>
      </div>

      <div className="mt-4 divide-y rounded-lg border">
        {postingResult.results.map((item, index) => {
          const status = String(
            item?.status || '',
          ).toUpperCase()

          const isSuccess =
            status === 'POSTED' ||
            status === 'ALREADY_POSTED'

          return (
            <div
              key={`${item?.document_id || 'document'}-${index}`}
              className="px-4 py-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                  Document ID:{' '}
                  {item?.document_id || 'Unknown'}
                </p>

                <span
                  className={
                    isSuccess
                      ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                      : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
                  }
                >
                  {isSuccess
                    ? `✓ ${status}`
                    : `✕ ${status || 'FAILED'}`}
                </span>
              </div>

              {item?.netsuite_record_id && (
                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  NetSuite Record ID:{' '}
                  <span className="font-medium">
                    {item.netsuite_record_id}
                  </span>
                </p>
              )}

              {item?.error && (
                <p className="mt-2 text-sm text-red-700">
                  {USER_FRIENDLY_MESSAGES.batchPost}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )}
      </>
    ) : (
      <>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-ink)]">
              NetSuite Validation
            </h2>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Vendor, Item, and Item/Subsidiary compatibility were checked
              against the connected NetSuite account.
            </p>
          </div>

          <span
            className={
              validationResult.status === 'VALIDATED'
                ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700'
                : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'
            }
          >
            {validationResult.status === 'VALIDATED'
              ? '✓ VALIDATION SUCCESSFUL'
              : '✕ VALIDATION FAILED'}
          </span>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Vendor
            </p>

            <p className="mt-1 font-medium">
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

          <div className="rounded-lg border p-4">
            <p className="text-xs text-[var(--color-muted)]">
              Items
            </p>

            <p className="mt-1 font-medium">
              {validationResult.summary
                ? `${Number(validationResult.summary.source_rows || 0)} source rows · ${Number(validationResult.summary.unique_netsuite_items || 0)} unique NetSuite items`
                : `${(validationResult.items || []).filter((item) => item.matched).length}/${(validationResult.items || []).length} matched`}
            </p>

            {validationResult.summary && (
              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {Number(validationResult.summary.matched_rows || 0)} matched ·{' '}
                {Number(validationResult.summary.unmatched_rows || 0)} unmatched
              </p>
            )}
          </div>
        </div>

        {(validationResult.errors || []).length > 0 && (
          <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-semibold text-red-800">
              Validation Errors
            </p>

            <div className="mt-2 space-y-2">
              {validationResult.errors.map((item, index) => {
                const errorReference =
                  getErrorReference(
                    validationResult.validation_id,
                    index,
                  )
                const diagnostic =
                  aiDiagnosticsByReference.get(
                    errorReference,
                  )

                return (
                  <ValidationErrorDisplay
                    key={`${item.type || 'error'}-${index}`}
                    errorItem={item}
                    diagnostic={diagnostic}
                    diagnosing={diagnosing}
                    diagnosticError={diagnosticError}
                  />
                )
              })}
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          {validationResult.status === 'VALIDATION_FAILED' && (
            <Button
              type="button"
              intent="secondary"
              onClick={handleValidateAgain}
              disabled={validating || saving || posting || diagnosing}
              isLoading={validating}
            >
              Validate Again
            </Button>
          )}

          {validationResult.status === 'VALIDATED' && (
            <Button
              type="button"
              onClick={handlePost}
              disabled={
                posting ||
                validating ||
                Boolean(
                  postingResult?.netsuite_record_id,
                )
              }
              isLoading={posting}
            >
              {postingResult?.netsuite_record_id
                ? 'Posted to NetSuite'
                : 'Post to NetSuite'}
            </Button>
          )}
        </div>

        {postingResult?.netsuite_record_id && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            Vendor Bill created successfully.
            <span className="ml-1 font-semibold">
              NetSuite Record ID:
            </span>{' '}
            {postingResult.netsuite_record_id}
          </div>
        )}
      </>
    )}
  </Card>
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
      AI mapping uses up to 2 attempts automatically
    </span>
  )}

  <Button
    type="button"
    intent="secondary"
    onClick={handleRefreshFields}
    disabled={
      refreshingFields ||
      mapping ||
      catalogueLoading ||
      !context?.connection_id
    }
    isLoading={refreshingFields}
  >
    Refresh Fields
  </Button>

  <Button
    type="button"
    onClick={handleMapFields}
    disabled={
      mapping ||
      catalogueLoading ||
      refreshingFields ||
      !context?.connection_id ||
      mapAttempt >= 2
    }
    isLoading={mapping || catalogueLoading}
  >
    {mapAttempt === 0
      ? 'Map Fields'
      : 'Run AI Mapping Again'}
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
                          {item.source_field_label || item.source_label || item.source_field_key}
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
                disabled={saving || mapping || validating || posting}
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
                  validating ||
                  posting ||
                  !mappings.length
                }
                isLoading={saving || validating}
              >
                Continue →
              </Button>
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}