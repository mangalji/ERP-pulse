import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import apiClient from '../../services/apiClient.js'
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

// function normalizeCatalogue(payload) {
//   const raw = payload?.data ?? payload ?? {}

//   const fieldContainer = raw?.fields
//   const nestedFields =
//     fieldContainer &&
//     !Array.isArray(fieldContainer)
//       ? [
//           ...(Array.isArray(fieldContainer.body)
//             ? fieldContainer.body
//             : []),
//           ...(Array.isArray(fieldContainer.column)
//             ? fieldContainer.column
//             : []),
//         ]
//       : []

//   const candidates =
//     nestedFields.length > 0
//       ? nestedFields
//       : Array.isArray(fieldContainer)
//         ? fieldContainer
//         : raw?.results ??
//           raw?.items ??
//           raw?.body_fields ??
//           []

//   const customFields = Array.isArray(raw?.custom_fields)
//     ? raw.custom_fields
//     : []

//   const source = [...candidates, ...customFields]

//   const normalized = []

//   source.forEach((field) => {
//     if (!field) return

//     const id =
//       field.id ||
//       field.field_id ||
//       field.internal_id ||
//       field.script_id ||
//       field.scriptId

//     if (!id) return

//     normalized.push({
//       id: String(id),
//       label:
//         field.label ||
//         field.display_label ||
//         field.name ||
//         String(id),
//       type:
//         field.type ||
//         field.field_type ||
//         field.datatype ||
//         'text',
//       scope:
//         field.scope ||
//         field.level ||
//         (field.sublist_id || field.sublist ? 'line' : 'body'),
//       reference_type:
//         field.reference_type ||
//         field.referenceRecordType ||
//         null,
//       custom:
//         Boolean(field.custom || field.is_custom),
//     })
//   })

//   return normalized
// }

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

// function suggestTarget(applicationField, catalogue) {
//   if (!catalogue.length) return null

//   const source = normalize(applicationField.key)
//   const sourceLabel = normalize(applicationField.label)

//   const scored = catalogue.map((field) => {
//     const target = normalize(field.id)
//     const targetLabel = normalize(field.label)

//     let score = 0

//     if (source === target || sourceLabel === targetLabel) {
//       score += 100
//     }

//     if (source && target.includes(source)) score += 35
//     if (source && source.includes(target)) score += 25

//     const sourceWords = new Set(
//       `${source} ${sourceLabel}`.split(' ').filter(Boolean),
//     )
//     const targetWords = new Set(
//       `${target} ${targetLabel}`.split(' ').filter(Boolean),
//     )

//     const overlap = [...sourceWords].filter((word) =>
//       targetWords.has(word),
//     ).length

//     score += overlap * 10

//     if (
//       applicationField.scope === 'line' &&
//       String(field.scope).toLowerCase() === 'line'
//     ) {
//       score += 20
//     }

//     if (
//       applicationField.scope !== 'line' &&
//       String(field.scope).toLowerCase() !== 'line'
//     ) {
//       score += 20
//     }

//     return { field, score }
//   })

//   scored.sort((a, b) => b.score - a.score)

//   return scored[0]?.field || null
// }

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

  const documentId = documentIds.length === 1
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
            source_field_key:
              field.key,
            source_field_label:
              field.label,
            source_scope:
              field.scope,
            source_datatype:
              field.type,

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

      const message =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to load NetSuite Vendor Bill fields.'

      setError(message)

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
      setError(
        'A connected NetSuite account is required before fields can be mapped.',
      )
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
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          "Unable to load NetSuite Vendor Bill fields.",
      )
      setNotice('')
    } finally {
      setMapping(false)
      setCatalogueLoading(false)
      setRefreshingFields(false)
    }
  }

  const handleRefreshFields = async () => {
  if (!context?.connection_id) {
    setError(
      'A connected NetSuite account is required before refreshing fields.',
    )
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

  // useEffect(() => {
  //   if (!catalogue.length || !applicationFields.length) {
  //     return
  //   }

  //   setMappings((current) => {
  //     const existingBySource = new Map(
  //       current.map((item) => [
  //         item.source_field_key,
  //         item,
  //       ]),
  //     )

  //     let changed = false

  //     const next = applicationFields.map((field) => {
  //       const existing = existingBySource.get(field.key)

  //       if (existing?.target_field_id) {
  //         return existing
  //       }

  //       const options =
  //         field.scope === 'line'
  //           ? catalogueOptionsByScope.line
  //           : catalogueOptionsByScope.body

  //       const suggestion = suggestTarget(field, options)

  //       const nextItem = {
  //         source_field_key: field.key,
  //         source_label: field.label,
  //         source_scope: field.scope,
  //         target_field_id: suggestion?.id || null,
  //         target_field_label: suggestion?.label || null,
  //         status: suggestion ? 'MAPPED' : 'UNRESOLVED',
  //         confidence: suggestion ? 0.75 : 0,
  //       }

  //       if (
  //         !existing ||
  //         existing.target_field_id !== nextItem.target_field_id ||
  //         existing.status !== nextItem.status
  //       ) {
  //         changed = true
  //       }

  //       return existing || nextItem
  //     })

  //     if (
  //       next.length !== current.length ||
  //       !next.every(
  //         (item, index) =>
  //           item?.source_field_key ===
  //           current?.[index]?.source_field_key,
  //       )
  //     ) {
  //       changed = true
  //     }

  //     return changed ? next : current
  //   })
  // }, [
  //   catalogue,
  //   applicationFields,
  //   catalogueOptionsByScope,
  // ])

  // const updateMapping = (sourceKey, targetId) => {
  //   const allOptions = catalogue
  //   const target = allOptions.find(
  //     (field) => field.id === targetId,
  //   )

  //   setMappings((current) =>
  //     current.map((item) =>
  //       item.source_field_key === sourceKey
  //         ? {
  //             ...item,
  //             target_field_id: target?.id || null,
  //             target_field_label: target?.label || null,
  //             status: target ? 'MAPPED' : 'UNRESOLVED',
  //             confidence: target ? 1 : 0,
  //           }
  //         : item,
  //     ),
  //   )
  //   setNotice('')
  // }

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
      setError(
        'A NetSuite connection is required to save mapping.',
      )
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
    } catch (err) {
      console.error(
        'Failed to save field mapping:',
        err,
      )
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

  const runValidation = async () => {
  if (!context?.connection_id) {
    setError(
      'A NetSuite connection is required for validation.',
    )
    return
  }

  if (!documentId) {
    setError(
       'This OCR result has not been saved yet. Please save it before continuing.',
    )
    return
  }

  try {
    setValidating(true)
    setError('')
    setNotice('')

    const result =
      await netsuiteApi.validateDocument(
        documentId,
        context.connection_id,
      )

    setValidationResult(result)

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
        'NetSuite validation failed. Review the errors and use Validate Again after correcting NetSuite data.',
      )
    }
  } catch (err) {
    console.error(
      'NetSuite document validation failed:',
      err,
    )

    setError(
      err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to validate the document against NetSuite.',
    )
  } finally {
    setValidating(false)
  }
}
const handleValidateAgain = async () => {
  await runValidation()
}
const handlePost = async () => {
  if (
    validationResult?.status !==
    'VALIDATED'
  ) {
    setError(
      'The document must be successfully validated before posting.',
    )
    return
  }

  if (!documentId || !context?.connection_id) {
    setError(
      'The OCR document or NetSuite connection is missing.',
    )
    return
  }

  try {
    setPosting(true)
    setError('')
    setNotice('')

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

    setError(
      err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to create the Vendor Bill in NetSuite.',
    )
  } finally {
    setPosting(false)
  }
}
  const handleContinue = async () => {
    if (!context?.connection_id) {
      setError(
        'A NetSuite connection is required for validation.',
      )
      return
    }

    if (!documentIds.length) {
      setError(
        'No saved OCR documents are available for validation.',
      )
      return
    }

    const vendorMapped = mappings.some(
      (item) =>
        item?.target_field_id &&
        ['entity', 'vendor'].includes(
          String(item.target_field_id).toLowerCase(),
        ),
    )

    const itemMapped = mappings.some(
      (item) =>
        item?.target_field_id === 'item' &&
        item?.source_scope === 'line',
    )

    if (!vendorMapped || !itemMapped) {
      setError(
        'Vendor and Item fields must be mapped before continuing.',
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

      const response = await apiClient.post(
        '/netsuite/ocr/batch/validate/',
        {
          document_ids: documentIds,
          connection_id: context.connection_id,
        },
      )

      const queued =
        response?.data?.data ??
        response?.data ??
        {}

      const jobId = queued?.job_id

      if (!jobId) {
        throw new Error(
          'NetSuite validation batch was created without a job ID.',
        )
      }

      sessionStorage.setItem(
        // CONTEXT_KEY,
        'ocr_netsuite_validation_job',
        JSON.stringify({
          // ...context,
          // document_ids: documentIds,
          // mapping_completed: true,
          // validation_job_id: String(jobId),
          job_id: String(jobId),
          connection_id: context.connection_id,
          document_ids: documentIds,
          created_at: Date.now(),
        }),
      )

      sessionStorage.setItem(
        CONTEXT_KEY,
        JSON.stringify({
          ...context,
          documents: context.documents || [],
          document_ids: documentIds,
          mapping_completed: true,
          validation_job_id: String(jobId),
        })
      )

      navigate('/app/ocr-test', {
        state: {
          validationJobId: String(jobId),
          documentIds,
          connectionId: context.connection_id,
        },
      })
    } catch (err) {
      console.error(
        'Failed to queue NetSuite reference validation:',
        err,
      )

      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to start NetSuite validation.',
      )
    } finally {
      setSaving(false)
    }
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
        {validationResult && (
  <Card className="p-5 sm:p-6">
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
          {
            (validationResult.items || []).filter(
              (item) => item.matched,
            ).length
          }
          /
          {(validationResult.items || []).length} matched
        </p>
      </div>
    </div>

    {(validationResult.errors || []).length > 0 && (
      <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-sm font-semibold text-red-800">
          Validation Errors
        </p>

        <div className="mt-2 space-y-2">
          {validationResult.errors.map(
            (item, index) => (
              <p
                key={`${item.type}-${index}`}
                className="text-sm text-red-700"
              >
                {item.message}
                {item.extracted_name
                  ? ` — ${item.extracted_name}`
                  : ''}
              </p>
            ),
          )}
        </div>
      </div>
    )}

    <div className="mt-5 flex flex-wrap justify-end gap-3">
      { false && validationResult.status ===
        'VALIDATION_FAILED' && (
        <Button
          type="button"
          intent="secondary"
          onClick={handleValidateAgain}
          disabled={
            validating ||
            saving ||
            posting
          }
          isLoading={validating}
        >
          Validate Again
        </Button>
      )}

      {validationResult.status ===
        'VALIDATED' && (
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
                  !mappings.length
                }
                isLoading={saving}
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