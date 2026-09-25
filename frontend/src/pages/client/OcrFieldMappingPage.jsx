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


const MAPPING_TOKEN_ALIASES = {
  qty: 'quantity',
  amt: 'amount',
  desc: 'description',
  no: 'number',
  num: 'number',
}

function normalizeMappingName(value) {
  return normalize(value)
    .split(' ')
    .filter(Boolean)
    .map((token) => MAPPING_TOKEN_ALIASES[token] || token)
    .join('')
}

function getMappingNameCandidates(field) {
  return [field?.label, field?.id, field?.key]
    .filter(Boolean)
    .map(normalizeMappingName)
    .filter(Boolean)
}

function findNameMatchedTarget(sourceField, actualFields) {
  if (sourceField.is_custom) return null

  const sourceCandidates = getMappingNameCandidates(sourceField)
  if (!sourceCandidates.length) return null

  const expectedScope =
    sourceField.scope === 'line' ? 'line' : 'body'

  const matches = actualFields.filter((target) => {
    if (target.scope !== expectedScope) return false
    if (target.is_custom) return false

    const targetCandidates = getMappingNameCandidates(target)
    return targetCandidates.some((targetName) =>
      sourceCandidates.includes(targetName),
    )
  })

  return matches.length === 1 ? matches[0] : null
}

function getApplicationFields(context) {
  const requested = context?.requested_fields
  const data = context?.data

  const standardKeys = Array.isArray(requested?.standard_fields) ? requested.standard_fields : []

  const customFields = Array.isArray(requested?.custom_fields) ? requested.custom_fields : []

  const headerFields = standardKeys.map((key) => ({
    key,
    label: STANDARD_LABELS[key] || key,
    is_custom: false,
    scope: 'body',
    type: 'text',
  }))

  const custom = customFields.map((field) => ({
    key: field.id || field.key,
    label: field.label || field.id || field.key,
    description: field.description || '',
    is_custom: true,
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
    is_custom: false,
    scope: 'body',
    type: typeof data?.[key] === 'number' ? 'number' : 'text',
  }))

  const fields = [...headerFields, ...custom, ...fallback]
  const deduped = new Map()

  fields.forEach((field) => {
    if (!field.key) return

    const identity =
      `${field.key}:${field.scope === 'line' ? 'line' : 'body'}`

    deduped.set(identity, field)
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
    const identity = `${key}:line`

    if (deduped.has(identity)) return
    deduped.set(identity, {
      key,
      label: STANDARD_LABELS[key] || key,
      is_custom: false,
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
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
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
  async () => {
    if (!context?.connection_id) {
      const message =
        'No NetSuite connection is available for this OCR result.'

      setError(message)
      throw new Error(message)
    }

    setCatalogueLoading(true)
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
          true,
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
            is_custom: Boolean(field.is_custom),

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

      const nextMappings = initialMappings.map((item) => {
        const savedMapping = savedBySource.get(
          item.source_field_key,
        )

        const savedMatchMethod =
          savedMapping?.metadata?.match_method

        if (
          savedMapping?.target_field_id &&
          savedMatchMethod === 'manual'
        ) {
          return {
            ...item,
            target_field_id: savedMapping.target_field_id,
            target_field_label: savedMapping.target_field_label || null,
            target_scope: savedMapping.target_scope || null,
            target_datatype: savedMapping.target_datatype || null,
            is_required: Boolean(savedMapping.is_required),
            is_custom: Boolean(savedMapping.is_custom),
            reference_type: savedMapping.reference_type || null,
            status: 'MAPPED',
            confidence: savedMapping.confidence ?? 1,
            metadata: {
              ...(savedMapping.metadata || {}),
              match_method: 'manual',
            },
          }
        }

        const target = findNameMatchedTarget(
          {
            key: item.source_field_key,
            label: item.source_field_label,
            id: item.source_field_key,
            scope: item.source_scope,
            is_custom: Boolean(item.is_custom),
          },
          actualFields,
        )

        if (!target) {
          return {
            ...item,
            target_field_id: null,
            target_field_label: null,
            target_scope: null,
            target_datatype: null,
            is_required: false,
            is_custom: false,
            reference_type: null,
            status: 'UNRESOLVED',
            confidence: null,
            candidates: [],
            metadata: { match_method: null },
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
          confidence: 1,
          candidates: [],
          metadata: { match_method: 'name' },
        }
      })

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
    }
  },
  [
    context,
    applicationFields,
  ],
)

  useEffect(() => {
    if (!context?.connection_id) return

    loadCatalogueAndSavedMappings().catch((err) => {
      console.error(
        'Automatic NetSuite field mapping load failed:',
        err,
      )
    })
  }, [context?.connection_id, loadCatalogueAndSavedMappings])

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

            metadata: {
              ...(item.metadata || {}),
              match_method: target ? 'manual' : null,
            },
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
    
      return true
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
    
      return false
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

  if (
    processingMode === 'SINGLE' &&
    !documentId
  ) {
    setError(
      'This OCR result has not been saved yet. Please save it before continuing.',
    )
    return
  }

  if (
    processingMode === 'MULTIPLE' &&
    !documentIds.length
  ) {
    setError(
      'No OCR documents are available for batch validation.',
    )
    return
  }

  try {
    setValidating(true)
    setError('')
    setNotice('')

    if (processingMode === 'SINGLE') {
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
            setError(
              statusData.error ||
                'NetSuite batch validation failed.',
            )
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

      throw new Error(
        'NetSuite batch validation timed out while waiting for the worker.',
      )
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
      err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Unable to validate the OCR document(s) against NetSuite.',
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
    setError(
      'A NetSuite connection is required before posting.',
    )
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
      setError(
        'The OCR document is missing.',
      )
      return
    }
    try{
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
    } catch(err) {
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
        throw new Error(
          'NetSuite batch posting did not return a job ID.',
        )
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
            setError(
              statusData.error ||
                'NetSuite batch posting failed.',
            )
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

      throw new Error(
        'NetSuite batch posting timed out while waiting for the worker.',
      )
    } catch (err) {
      console.error(
        'NetSuite batch Vendor Bill posting failed:',
        err,
      )

      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to post the validated OCR documents to NetSuite.',
      )
    } finally {
      setPosting(false)
    }

    return
  }

  setError(
    'Unsupported OCR processing mode.',
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
                            {item?.error && (
                              <p className="text-sm text-red-700">
                                {item.error}
                              </p>
                            )}

                            {errors.map((errorItem, errorIndex) => (
                              <p
                                key={`${errorItem?.type || 'error'}-${errorIndex}`}
                                className="text-sm text-red-700"
                              >
                                {errorItem?.message ||
                                  String(errorItem)}
                                {errorItem?.extracted_name
                                  ? ` — ${errorItem.extracted_name}`
                                  : ''}
                              </p>
                            ))}
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
      disabled={validating || saving || posting}
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
                  {item.error}
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
              Vendor and Item existence was checked against the connected
              NetSuite account.
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
              {validationResult.errors.map((item, index) => (
                <p
                  key={`${item.type}-${index}`}
                  className="text-sm text-red-700"
                >
                  {item.message}
                  {item.extracted_name
                    ? ` — ${item.extracted_name}`
                    : ''}
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          {validationResult.status === 'VALIDATION_FAILED' && (
            <Button
              type="button"
              intent="secondary"
              onClick={handleValidateAgain}
              disabled={validating || saving || posting}
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
          <div>
            <h2 className="text-base font-semibold text-[var(--color-ink)]">
              NetSuite Field Mapping
            </h2>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Fields are automatically matched by normalized field names. Unmatched or custom fields can be mapped manually below.
            </p>
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

          {!catalogueLoading && catalogue.length === 0 && context?.connection_id && (
            <div className="mt-5 rounded-lg border border-dashed border-[var(--color-border)] p-6 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                No NetSuite Vendor Bill fields were returned.
              </p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Check the NetSuite connection and try again.
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
                              ? item.metadata?.match_method === 'name'
                                ? 'Auto-matched by name'
                                : 'Mapped'
                              : 'Unresolved — select manually'}
                          </span>

                          {item.metadata?.match_method === 'name' && (
                            <span className="text-[11px] text-[var(--color-muted)]">
                              Exact normalized name match
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
                disabled={saving || validating || posting}
                isLoading={saving}
              >
                Save Mapping
              </Button>

              <Button
                type="button"
                onClick={handleContinue}
                disabled={
                  saving ||
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