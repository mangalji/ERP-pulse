import { useEffect, useMemo, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import apiClient from '../../services/apiClient.js'
import { formatDateTime } from '../../utils/formatDate.js'
import { netsuiteApi } from '../../services/netsuite.js'

const DATA_TYPE_OPTIONS = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'currency', label: 'Currency' },
]

const SCOPE_OPTIONS = [
  { value: 'header', label: 'Header' },
  { value: 'line', label: 'Line' },
]

function createFieldId(prefix = 'field') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const DEFAULT_NETSUITE_FIELD_MAPPINGS = {
  invoice_number: {
    id: 'tranid',
    scope: 'body',
  },
  invoice_date: {
    id: 'trandate',
    scope: 'body',
  },
  due_date: {
    id: 'duedate',
    scope: 'body',
  },
  vendor_name: {
    id: 'entity',
    scope: 'body',
  },
  subsidiary: {
    id: 'subsidiary',
    scope: 'body',
  },
  currency: {
    id: 'currency',
    scope: 'body',
  },
  subtotal: {
    id: 'total',
    scope: 'body',
  },
  tax_amount: {
    id: 'taxtotal',
    scope: 'body',
  },
  tax_rate: {
    id: 'taxRate1',
    scope: 'line',
    preferredSublistId: 'item',
  },
  total_amount: {
    id: 'grossAmt',
    scope: 'line',
    preferredSublistId: 'item'
  },
  payment_terms: {
    id: 'paymentmethod',
    scope: 'body',
  },
  description: {
    id: 'item',
    scope: 'line',
    preferredSublistId: 'item',
  },
  quantity: {
    id: 'quantity',
    scope: 'line',
    preferredSublistId: 'item',
  },
  unit_price: {
    id: 'rate',
    scope: 'line',
    preferredSublistId: 'item',
  },
  amount: {
    id: 'userTotal',
    scope: 'body',
    preferredSublistId: 'item',
  },
}

function resolveDefaultNetSuiteMapping(field, options) {
  const mapping = DEFAULT_NETSUITE_FIELD_MAPPINGS[field?.key]

  if (!mapping || !Array.isArray(options)) {
    return null
  }

  const targetId = String(mapping.id || '')
    .trim()
    .toLowerCase()

  const targetScope = String(mapping.scope || '')
    .trim()
    .toLowerCase()

  if (!targetId || !targetScope) {
    return null
  }

  const candidates = options.filter(
    (option) =>
      String(option?.id || '').trim().toLowerCase() === targetId &&
      String(option?.scope || '').trim().toLowerCase() === targetScope,
  )

  if (!candidates.length) {
    return null
  }

  const preferredSublistId = String(
    mapping.preferredSublistId || '',
  )
    .trim()
    .toLowerCase()

  const selected =
    candidates.find(
      (option) =>
        String(option?.sublist_id || '').trim().toLowerCase() ===
        preferredSublistId,
    ) || candidates[0]

  return {
    netsuite_field_id: selected.id,
    netsuite_field_scope: selected.scope,
    netsuite_field_sublist_id: selected.sublist_id || '',
  }
}

function normalizeCatalogField(field) {
  return {
    id: `standard-${field?.scope || 'header'}-${field?.key || createFieldId('standard')}`,
    key: field?.key || '',
    original_key: field?.key || '',
    label: field?.label || field?.key || '',
    description:
      field?.questionaire ||
      field?.description ||
      field?.label ||
      '',
    data_type: field?.data_type || 'text',
    scope: field?.scope === 'line' ? 'line' : 'header',
    
    // NetSuite mapping
    netsuite_field_id:
      field?.netsuite_field_id ||
      field?.field_id ||
      '',
    
    netsuite_field_scope:
      field?.netsuite_field_scope ||
      field?.target_scope ||
      '',

    netsuite_field_sublist_id:
      field?.netsuite_field_sublist_id ||
      field?.sublist_id ||
      '',

    standard: true,
    enabled: field?.enabled !== false,
  }
}

function normalizeCustomField(field, index = 0) {
  return {
    id: field?.id || createFieldId(`custom-${index}`),
    key: field?.key || field?.label || '',
    original_key: null,
    label: field?.label || field?.key || '',
    description:
      field?.description ||
      field?.questionaire ||
      field?.label ||
      '',
    data_type: field?.data_type || 'text',
    scope: field?.scope === 'line' ? 'line' : 'header',

    // NetSuite mapping
    netsuite_field_id:
      field?.netsuite_field_id ||
      field?.field_id ||
      '',

    netsuite_field_scope:
      field?.netsuite_field_scope ||
      field?.target_scope ||
      '',

    netsuite_field_sublist_id:
      field?.netsuite_field_sublist_id ||
      field?.sublist_id ||
      '',
    
    standard: false,
    enabled: field?.enabled !== false,
  }
}

function normalizeTemplateConfig(config) {
  if (!config || typeof config !== 'object') {
    return {
      standard_fields: [],
      standard_field_overrides: {},
      custom_fields: [],
      disabled_standard_fields: [],
      disabled_custom_fields: [],
    }
  }

  return {
    standard_fields: Array.isArray(config.standard_fields)
      ? config.standard_fields
      : [],
    standard_field_overrides:
      config.standard_field_overrides &&
      typeof config.standard_field_overrides === 'object'
        ? config.standard_field_overrides
        : {},
    custom_fields: Array.isArray(config.custom_fields)
      ? config.custom_fields.map((field, index) =>
          normalizeCustomField(field, index),
        )
      : [],
    disabled_standard_fields: Array.isArray(config.disabled_standard_fields)
      ? config.disabled_standard_fields
      : [],
    disabled_custom_fields: Array.isArray(config.disabled_custom_fields)
      ? config.disabled_custom_fields.map((field, index) =>
          normalizeCustomField(field, index),
        )
      : [],
  }
}

function normalizeNetSuiteFieldCatalogue(payload) {
  const raw = payload?.data ?? payload ?? {}
  const fieldContainer = raw?.fields

  const nestedFields =
    fieldContainer && !Array.isArray(fieldContainer)
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

  const customFields = Array.isArray(raw?.custom_fields)
    ? raw.custom_fields
    : []

  const deduped = new Map()

  ;[...candidates, ...customFields].forEach((field) => {
    if (!field) return

    const id = String(
      field.id ||
      field.field_id ||
      field.internal_id ||
      field.script_id ||
      field.scriptId ||
      '',
    ).trim()

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
    )
      .trim()
      .toLowerCase()

    const scope =
      ['line', 'column', 'sublist'].includes(rawScope)
        ? 'line'
        : 'body'

    const sublistId = String(
      field.sublist_id ||
      field.sublistId ||
      field.sublist ||
      '',
    )
      .trim()
      .toLowerCase()

    /*
     * Keep item and expense as separate options.
     *
     * Example:
     * taxrate1:line:item
     * taxrate1:line:expense
     * taxrate1:line:
     *
     * These are three different catalogue entries initially.
     */
    const key = `${id}:${scope}:${sublistId}`

    if (deduped.has(key)) {
      return
    }

    deduped.set(key, {
      id,
      label:
        field.label ||
        field.display_label ||
        field.name ||
        id,
      scope,
      sublist_id: sublistId,
      sublist_contexts: sublistId
        ? [sublistId]
        : [],
      type:
        field.data_type ||
        field.type ||
        field.field_type ||
        'text',
      is_required: Boolean(field.is_required),
      is_custom: Boolean(
        field.is_custom ??
        field.custom,
      ),
      reference_type:
        field.reference_type ||
        field.referenceRecordType ||
        null,
    })
  })

  const entries = [...deduped.values()]

  /*
   * If a field has one or more real sublist contexts
   * (item / expense), remove only its generic line entry.
   *
   * Example:
   *
   * taxrate1 | line | expense
   * taxrate1 | line | item
   * taxrate1 | line |
   *
   * becomes:
   *
   * taxrate1 | line | expense
   * taxrate1 | line | item
   *
   * But if only:
   *
   * taxrate1 | line |
   *
   * exists, keep it.
   */
  const contextualKeys = new Set()

  entries.forEach((entry) => {
    if (entry.sublist_id) {
      contextualKeys.add(
        `${String(entry.id || '').trim().toLowerCase()}:${String(
        entry.scope || '',
      )
        .trim()
        .toLowerCase()}`,
      )
    }
  })

  return entries.filter((entry) => {
    if (!entry.sublist_id) {

      const key = `${String(entry.id || '').trim().toLowerCase()}:${String(
      entry.scope || '',
    )
      .trim()
      .toLowerCase()}`

      if (contextualKeys.has(key)) {
        return false
      }
    }

    return true
  })
}

function NetSuiteFieldCombobox({
  field,
  options,
  loading,
  value,
  onChange,
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const selectedOption = options.find(
  (option) => {
    const [
      selectedId = '',
      selectedScope = '',
      selectedSublistId = '',
    ] = String(value || '').split(':')

    return (
      option.id === selectedId &&
      option.scope === selectedScope &&
      (option.sublist_id || '') === selectedSublistId
    )
  },
)

  const getNetSuiteFieldContext = (option) => {
    const contexts = Array.isArray(option?.sublist_contexts)
      ? option.sublist_contexts
          .map((context) =>
            String(context || '').trim().toLowerCase(),
          )
          .filter(Boolean)
      : []
        
    if (contexts.length > 0) {
      return contexts.join('/')
    }
  
    return String(
      option?.scope || '',
    ).trim().toLowerCase()
  }

  const getNetSuiteFieldDisplay = (option) => {
  const scope = String(
    option?.scope || '',
  )
    .trim()
    .toLowerCase()

  const sublistId = String(
    option?.sublist_id || '',
  )
    .trim()
    .toLowerCase()

  if (scope && sublistId) {
    return `${option.label} (${option.id}) (${scope}) (${sublistId})`
  }

  if (scope) {
    return `${option.label} (${option.id}) (${scope})`
  }

  if (sublistId) {
    return `${option.label} (${option.id}) (${sublistId})`
  }

  return `${option.label} (${option.id})`
}

  const filteredOptions = useMemo(() => {
    const query = search.trim().toLowerCase()

    if (!query) return options

    return options.filter((option) => {
      const label = String(
        option.label || '',
      ).toLowerCase()

      const id = String(
        option.id || '',
      ).toLowerCase()

      const context = getNetSuiteFieldContext(option)

      return (
        label.includes(query) ||
        id.includes(query) ||
        context.includes(query)
      )
    })
  }, [options, search])

  return (
    <div className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        disabled={loading}
        className="flex w-full items-center justify-between rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-left text-xs outline-none focus:border-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className={selectedOption ? 'text-[var(--color-ink)]' : 'text-[var(--color-muted)]'}>
          {loading
            ? 'Loading NetSuite fields...'
            : selectedOption
              ? getNetSuiteFieldDisplay(selectedOption)
              : 'Select NetSuite field'}
        </span>

        <span className="ml-2 text-xs">
          {open ? '▲' : '▼'}
        </span>
      </button>

      {open && !loading && (
        <div className="absolute left-0 right-0 z-50 mt-1 rounded-md border border-[var(--color-border)] bg-white shadow-lg">
          <div className="border-b border-[var(--color-border)] p-2">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search NetSuite field..."
              autoFocus
              className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          <div className="max-h-72 overflow-y-auto">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((target) => (
                <button
                  key={`${target.id}:${target.scope}:${target.sublist_id || ''}`}
                  type="button"
                  onClick={() => {
                    onChange({
                      fieldId: target.id,
                      scope: target.scope,
                      sublistId: target.sublist_id || '',
                    })
                    setOpen(false)
                    setSearch('')
                  }}
                  className={`block w-full px-3 py-2 text-left text-xs hover:bg-[var(--color-canvas)] ${
                    `${target.id}:${target.scope}:${target.sublist_id || ''}` === value? 'bg-[var(--color-canvas)] font-medium': ''
                  }`}
                >
                  {getNetSuiteFieldDisplay(target)}
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-xs text-[var(--color-muted)]">
                No NetSuite fields found.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function getCreatedBy(template) {
  const creator =
    template?.created_by_user ??
    template?.created_by ??
    template?.createdBy

  // Prefer actual user details over a UUID.
  if (creator && typeof creator === 'object') {
    const name =
      creator.full_name ||
      creator.name ||
      creator.username ||
      creator.email ||
      creator.display_name

    if (name) return name
  }

  // Prefer explicit name fields before falling back to the ID.
  const name =
    template?.created_by_name ||
    template?.created_by_full_name ||
    template?.created_by_username ||
    template?.created_by_email

  if (name) return name

  // Last resort: display the raw value if no user name is available.
  if (typeof creator === 'string' || typeof creator === 'number') {
    return String(creator)
  }

  return '—'
}

function getErrorMessage(error, fallback) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.response?.data?.name?.[0] ||
    error?.response?.data?.fields_config?.[0] ||
    error?.response?.data?.error ||
    fallback
  )
}


function ActionIcon({ name, className = 'h-5 w-5' }) {
  const common = {
    className,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  if (name === 'view') {
    return (
      <svg {...common}>
        <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    )
  }

  if (name === 'edit') {
    return (
      <svg {...common}>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" />
      </svg>
    )
  }

  if (name === 'delete') {
    return (
      <svg {...common}>
        <path d="M3 6h18" />
        <path d="M8 6V4h8v2" />
        <path d="m19 6-1 14H6L5 6" />
        <path d="M10 10v6M14 10v6" />
      </svg>
    )
  }

  if (name === 'file') {
    return (
      <svg {...common}>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M9 8h6M9 12h6" />
      </svg>
    )
  }

  if (name === 'back') {
    return (
      <svg {...common}>
        <path d="m15 18-6-6 6-6" />
        <path d="M9 12h12" />
      </svg>
    )
  }

  return null
}

export default function FileTemplatePage() {
  const [catalog, setCatalog] = useState(null)
  const [templates, setTemplates] = useState([])
  const [connection, setConnection] = useState(null)
  const [isCompanyAdmin, setIsCompanyAdmin] = useState(false)
  const [netSuiteFields, setNetSuiteFields] = useState([])
  const [netSuiteFieldsLoading, setNetSuiteFieldsLoading] = useState(false)
  const [catalogueLoaded, setCatalogueLoaded] = useState(false)
  const [refreshingCatalogue, setRefreshingCatalogue] = useState(false)
  const sortedNetSuiteFields = useMemo(
    () =>
      [...netSuiteFields].sort((a, b) => {
        const idCompare = String(a.id || '').localeCompare(
          String(b.id || ''),
          undefined,
          { sensitivity: 'base' },
        )

        if (idCompare !== 0) {
          return idCompare
        }

        return String(
          a.sublist_id || a.scope || '',
        ).localeCompare(
          String(
            b.sublist_id || b.scope || '',
          ),
          undefined,
          { sensitivity: 'base' },
        )
      }),
    [netSuiteFields],
  )
  const [selectedTemplateId, setSelectedTemplateId] = useState(null)
  const [templateName, setTemplateName] = useState('')
  const [mode, setMode] = useState('empty') // empty | view | edit | new
  const isDetailPage = mode !== 'empty'
  const [highlightedFieldId, setHighlightedFieldId] = useState(null)

  // One unified editor list for standard + custom fields.
  const [fields, setFields] = useState([])

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const catalogFields = useMemo(() => {
    if (!catalog) return []

    return [
      ...(Array.isArray(catalog.header_fields)
        ? catalog.header_fields
        : []),
      ...(Array.isArray(catalog.line_fields)
        ? catalog.line_fields
        : []),
    ]
  }, [catalog])

  const getConnectionId = (value) => (
  value?.id ||
  value?.connection_id ||
  value?.connection?.id ||
  null
)

const loadNetSuiteFields = async (connectionValue) => {
  if (catalogueLoaded){
    return netSuiteFields
  }

  const connectionId = getConnectionId(connectionValue)

  if (!connectionId) {
    setNetSuiteFields([])
    setCatalogueLoaded(true)
    return []
  }

  setNetSuiteFieldsLoading(true)

  try {
    const response = await apiClient.get(
      '/netsuite/ocr/field-catalogue/',
      {
        params: {
          connection_id: connectionId,
          record_type: 'vendorBill',

        },
      },
    )

    const payload =
      response?.data?.data ??
      response?.data ??
      {}

      const fields = normalizeNetSuiteFieldCatalogue(payload)

      setNetSuiteFields(fields)
      setCatalogueLoaded(true)
      return fields

    
  } catch (err) {
    console.error(
      'Failed to load NetSuite field catalogue:',
      err,
    )
    setNetSuiteFields([])
    setCatalogueLoaded(false)
    return []

  } finally {
    setNetSuiteFieldsLoading(false)
  }
}

const handleRefreshNetSuiteFields = async () => {
  if (!isCompanyAdmin || refreshingCatalogue) {
    return
  }

  const connectionId = getConnectionId(connection)

  if (!connectionId) {
    setError('No active NetSuite connection is available.')
    return
  }

  setRefreshingCatalogue(true)
  setError('')
  setMessage('')

  try {
    const response = await apiClient.post(
      '/netsuite/ocr/field-catalogue/',
      {
        connection_id: connectionId,
        record_type: 'vendorBill',
      },
    )

    const payload =
      response?.data?.data ??
      response?.data ??
      {}

    const fields = normalizeNetSuiteFieldCatalogue(payload)

    setNetSuiteFields(fields)
    setCatalogueLoaded(true)

    if (payload?.refresh_failed || payload?.source !== 'netsuite') {
      setError(
        payload?.error ||
        response?.data?.message ||
        'Refresh failed. The saved catalogue has been preserved.',
      )
    } else {
      const added = Number(payload?.added_fields_count ?? 0)

      setMessage(
        added > 0
          ? `Refresh successful. ${added} new field(s) added.`
          : 'Refresh successful. No new fields found; existing fields were preserved.',
      )
    }
  } catch (err) {
    setError(
      getErrorMessage(
        err,
        'Unable to refresh NetSuite fields.',
      ),
    )
  } finally {
    setRefreshingCatalogue(false)
  }
}

  const loadCatalog = async () => {
    const response = await apiClient.get('/ocr/extraction-fields/')
    const data = response?.data?.data ?? response?.data ?? {}

    setCatalog(data)

    return data
  }

  const loadTemplates = async () => {
    const response = await apiClient.get('/ocr/extraction-templates/')
    const data = response?.data?.data ?? response?.data ?? []
    const items = Array.isArray(data) ? data : []

    setTemplates(items)

    return items
  }

  const loadPage = async () => {
    setLoading(true)
    setError('')

    try {

      const [connectionPayload,profilePayload] = await Promise.all([
        netsuiteApi.getMyConnection().catch(()=>null),
        apiClient.get('/client/me/').catch(()=>null),
    ])

  const connectionData =
    connectionPayload?.data ??
    connectionPayload ??
    null

  setConnection(connectionData)

  const profile =
    profilePayload?.data?.data ??
    profilePayload?.data ??
    {}

    const roleValues = profile?.roles ?? profile?.user?.roles ?? []

    const normalizedRoles = (
      Array.isArray(roleValues) ? roleValues : []
    ).map((role) => {
        if (typeof role === 'string') return role
        return (
          role?.slug ||
          role?.code ||
          role?.name ||
          role?.role_name ||
          ''
        )
      }).map((role) =>
        String(role)
          .trim()
          .toLowerCase()
          .replace(/[-_]/g, ' ')
      )

      const primaryRole = String(
        profile?.user?.role?.name ||
        profile?.role?.name ||
        profile?.user?.role_name ||
        '',
      ).trim()
        .toLowerCase()
        .replace(/[-_]/g, ' ')

        setIsCompanyAdmin(
          normalizedRoles.includes('company admin') ||
          primaryRole === 'company admin',
        )

  await Promise.all([
    loadCatalog(),
    loadTemplates(),
    loadNetSuiteFields(connectionData),
  ])

  // Keep the editor empty until the user opens a template or starts a new one.
  setFields([])
  setMode('empty')
} catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to load file templates. Please try again.',
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPage()
  }, [])

  const createDefaultFields = (availableFields=sortedNetSuiteFields) =>
  catalogFields
    .filter(
      (catalogField) =>
        String(catalogField?.key || '').trim().toLowerCase() !==
        'customer_name',
    )
    .map((catalogField) => {
      const field = normalizeCatalogField(catalogField)

      const defaultMapping = resolveDefaultNetSuiteMapping(
        field,
        availableFields,
      )

      return defaultMapping
        ? {
            ...field,
            ...defaultMapping,
          }
        : field
    })

  const resetEditor = (availableFields = sortedNetSuiteFields) => {
    setSelectedTemplateId(null)
    setTemplateName('')
    setFields(createDefaultFields(availableFields))
    setMode('new')
    setHighlightedFieldId(null)
    setMessage('')
    setError('')
  }

  const openTemplate = async (template, nextMode = 'view') => {
    if (!template?.id) return

    if (nextMode === 'edit'){
      await loadNetSuiteFields(connection)
    }

    selectTemplate(template, nextMode)
  }

  const startNewTemplate = async () => {
    const loadedFields = await loadNetSuiteFields(connection)

    const sortedFields = [...loadedFields].sort((a,b)=>{
      const idCompare = String(a.id || '').localeCompare(
        String(b.id ||'',
          undefined,
          {sensitivity:'base'},
        )
      )
        if (idCompare !==0 ) return idCompare

        return String(a.sublist_id || a.scope || '').localeCompare(
          String(b.sublist_id || b.scope || ""),undefined,{sensitivity:'base'},
        )
    })

    resetEditor(sortedFields)
  }

  const handleBackToTemplates = () => {
    setSelectedTemplateId(null)
    setTemplateName('')
    setFields([])
    setMode('empty')
    setHighlightedFieldId(null)
    setError('')
    setMessage('')
  }

  const selectTemplate = (template, nextMode = 'view') => {
    const config = normalizeTemplateConfig(template?.fields_config)
    const selectedStandardKeys = new Set([
      ...config.standard_fields,
      ...config.disabled_standard_fields,
    ])
    const disabledStandardKeys = new Set(config.disabled_standard_fields)

    const standardFields = catalogFields
      .filter((field) => selectedStandardKeys.has(field?.key))
      .map((field) => {
        const normalized = normalizeCatalogField(field)
        const override = config.standard_field_overrides?.[normalized.original_key]

        return {
          ...normalized,
          label: override?.label || normalized.label,
          description:
            override?.description ||
            override?.questionaire ||
            normalized.description,
          data_type: override?.data_type || normalized.data_type,
          scope:
            override?.scope === 'line'
              ? 'line'
              : override?.scope === 'header'
                ? 'header'
                : normalized.scope,
          netsuite_field_id:
            override?.netsuite_field_id ||
            normalized.netsuite_field_id ||
            '',

          netsuite_field_scope:
            override?.netsuite_field_scope ||
            normalized.netsuite_field_scope ||
            '',

          netsuite_field_sublist_id:
            override?.netsuite_field_sublist_id ||
            normalized.netsuite_field_sublist_id ||
            '',
          enabled: !disabledStandardKeys.has(normalized.original_key) &&
            override?.enabled !== false,
        }
      })

    const customFields = [
      ...config.custom_fields.map((field, index) =>
        normalizeCustomField({ ...field, enabled: field?.enabled !== false }, index),
      ),
      ...config.disabled_custom_fields.map((field, index) =>
        normalizeCustomField({ ...field, enabled: false }, index + config.custom_fields.length),
      ),
    ]

    setSelectedTemplateId(template?.id || null)
    setTemplateName(template?.name || '')
    setFields([...standardFields, ...customFields])
    setMode(nextMode)
    setHighlightedFieldId(null)
    setMessage('')
    setError('')
  }

  const addCustomField = () => {
    const id = createFieldId('custom')

    setFields((current) => [
      {
        id,
        key: '',
        original_key: null,
        label: '',
        description: '',
        data_type: 'text',
        scope: 'header',

        // NetSuite mapping
        netsuite_field_id: '',
        netsuite_field_scope: '',
        netsuite_field_sublist_id: '',
  
        standard: false,
        enabled: true,
      },
      ...current,
    ])
    setMode('edit')
    setHighlightedFieldId(id)
    setMessage('')
    setError('')
  }

  useEffect(() => {
    if (!highlightedFieldId) return
    const fieldRow = document.getElementById(`template-field-${highlightedFieldId}`)
    fieldRow?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    fieldRow?.querySelector('input')?.focus()
    const timeout = window.setTimeout(() => setHighlightedFieldId(null), 2200)
    return () => window.clearTimeout(timeout)
  }, [highlightedFieldId, fields])

  const updateField = (id, patch) => {
    setFields((current) =>
      current.map((field) =>
        field.id === id
          ? { ...field, ...patch }
          : field,
      ),
    )

    setMessage('')
    setError('')
  }

  const toggleField = (id) => {
    setFields((current) =>
      current.map((field) =>
        field.id === id ? { ...field, enabled: field.enabled === false } : field,
      ),
    )
    setMessage('')
    setError('')
  }

  const buildFieldsConfig = () => {
    const standardFields = fields
      .filter((field) => field.standard && field.enabled !== false)
      .map((field) => field.original_key || field.key?.trim())
      .filter(Boolean)

    const disabledStandardFields = fields
      .filter((field) => field.standard && field.enabled === false)
      .map((field) => field.original_key || field.key?.trim())
      .filter(Boolean)

    const standardFieldOverrides = {}
    fields
      .filter((field) => field.standard)
      .forEach((field) => {
        const key = field.original_key || field.key?.trim()
        if (!key) return

        standardFieldOverrides[key] = {
          label: field.label?.trim(),

          netsuite_field_id:
            field.netsuite_field_id?.trim() || '',

          netsuite_field_scope:
            field.netsuite_field_scope || '',

          netsuite_field_sublist_id:
            field.netsuite_field_sublist_id || '',

          description: field.description?.trim(),
          questionaire: field.description?.trim(),
          data_type: field.data_type,
          scope: field.scope,
          enabled: field.enabled !== false,
        }
      })

    const serializeCustomField = (field) => ({
      key: field.key?.trim() || field.label?.trim(),

      netsuite_field_id:
        field.netsuite_field_id?.trim() || '',

      netsuite_field_scope:
        field.netsuite_field_scope || '',

      netsuite_field_sublist_id:
        field.netsuite_field_sublist_id || '',

      label: field.label?.trim(),
      description: field.description?.trim(),
      questionaire: field.description?.trim(),
      data_type: field.data_type,
      scope: field.scope,
      enabled: field.enabled !== false,
    })

    return {
      standard_fields: standardFields,
      disabled_standard_fields: disabledStandardFields,
      standard_field_overrides: standardFieldOverrides,
      custom_fields: fields
        .filter((field) => !field.standard && field.enabled !== false)
        .map(serializeCustomField),
      disabled_custom_fields: fields
        .filter((field) => !field.standard && field.enabled === false)
        .map(serializeCustomField),
    }
  }

  const validateBeforeSave = (name = templateName) => {
    if (!name.trim()) {
      return 'Template name is required.'
    }

    const activeFields = fields.filter((field) => field.enabled !== false)
    if (!activeFields.length) {
      return 'Use at least one field in the template before saving.'
    }

    const seenKeys = new Set()

    for (const field of activeFields) {
      const label = field.label?.trim()

      if (!label) {
        return 'Every field must have a Field Name.'
      }

      
      if (!field.description?.trim()) {
        return `Questionaire is required for "${label}".`
      }
      
      if (!field.netsuite_field_id?.trim()) {
        return `NetSuite Field ID is required for "${label}".`
      }
      
      const key =
        field.original_key ||
        field.key?.trim() ||
        label
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_+|_+$/g, '')

      if (!key) {
        return `Unable to generate an internal key for "${label}".`
      }

      const normalizedKey = key.toLowerCase()

      if (seenKeys.has(normalizedKey)) {
        return `Duplicate field: "${label}".`
      }

      seenKeys.add(normalizedKey)
    }

    return ''
  }

  const handleSave = async ({ saveAs = false } = {}) => {
    setError('')
    setMessage('')

    let nameToSave = templateName.trim()
    if (saveAs) {
      const suggestedName = selectedTemplateId
        ? `${templateName.trim()} (Copy)`
        : templateName.trim()
      const enteredName = window.prompt('Name for the new template:', suggestedName)
      if (enteredName === null) return
      nameToSave = enteredName.trim()
      if (!nameToSave) {
        setError('Template name is required for Save As.')
        return
      }
    }

    const validationError = validateBeforeSave(nameToSave)
    if (validationError) {
      setError(validationError)
      return
    }
    if (!nameToSave) {
      setError('Template name is required.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        name: nameToSave,
        fields_config: buildFieldsConfig(),
      }

      const shouldCreate = saveAs || !selectedTemplateId
      const response = shouldCreate
        ? await apiClient.post('/ocr/extraction-templates/', payload)
        : await apiClient.patch(
            `/ocr/extraction-templates/${selectedTemplateId}/`,
            payload,
          )

      const saved = response?.data?.data ?? response?.data ?? {}
      const updatedTemplates = await loadTemplates()

      if (saved?.id) {
        const refreshedSaved = updatedTemplates.find(
          (item) => String(item.id) === String(saved.id),
        )
        if (refreshedSaved) {
          selectTemplate(refreshedSaved, 'view')
        } else {
          setSelectedTemplateId(saved.id)
          setTemplateName(saved.name || nameToSave)
          setMode('view')
        }
      } else if (shouldCreate) {
        const created = updatedTemplates.find((item) => item.name === nameToSave)
        if (created) {
          selectTemplate(created, 'view')
        } else {
          setSelectedTemplateId(null)
          setTemplateName(nameToSave)
          setMode('view')
        }
      } else {
        const refreshed = updatedTemplates.find(
          (item) => String(item.id) === String(selectedTemplateId),
        )
        if (refreshed) {
          selectTemplate(refreshed, 'view')
        } else {
          setMode('view')
        }
      }

      setMessage(
        saveAs
          ? 'A new template was created. The original template was not changed.'
          : shouldCreate
            ? 'Template created successfully.'
            : 'Template updated successfully.',
      )
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to save the template.'))
    } finally {
      setSaving(false)
    }
  }

  const handleSetPreferred = async (template) => {
    if (!template?.id || template.is_preferred) {
      return
    }

    setError('')
    setMessage('')

    try {
      await apiClient.patch(
        `/ocr/extraction-templates/${template.id}/`,
        {
          is_preferred: true,
        },
      )
    
      await loadTemplates()
    
      setMessage(
        `"${template.name}" is now your preferred template.`,
      )
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to set preferred template.',
        ),
      )
    }
  }

  const handleDeleteTemplate = async (template) => {
    if (!template?.id) return
    const confirmed = window.confirm(
      `Delete "${template.name}" template? This action cannot be undone.`,
    )
    if (!confirmed) return

    setDeleting(true)
    setError('')
    setMessage('')
    try {
      await apiClient.delete(`/ocr/extraction-templates/${template.id}/`)
      await loadTemplates()
      if (String(selectedTemplateId) === String(template.id)) {
        setSelectedTemplateId(null)
        setTemplateName('')
        setFields([])
        setMode('empty')
      }
      setMessage(`"${template.name}" template deleted successfully.`)
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to delete the template.'))
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <ClientLayout>
        <div className="p-6 text-sm text-[var(--color-muted)]">
          Loading file templates...
        </div>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout>
      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            {isDetailPage && (
              <button
                type="button"
                onClick={handleBackToTemplates}
                className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-[var(--color-muted)] transition hover:text-[var(--color-ink)]"
              >
                <ActionIcon name="back" />
                Back to templates
              </button>
            )}
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              {isDetailPage
                ? mode === 'new'
                  ? 'New Template'
                  : mode === 'edit'
                    ? `Edit ${templateName || 'Template'}`
                    : templateName || 'Template Details'
                : 'File Templates'}
            </h1>
            {!isDetailPage && (
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Create reusable OCR extraction templates and define the fields that should be extracted from uploaded documents.
              </p>
            )}
          </div>
          {!isDetailPage && (
            <div className="flex flex-wrap items-center gap-2">
              {isCompanyAdmin && (
                <Button
                  type="button"
                  onClick={handleRefreshNetSuiteFields}
                  disabled={
                    refreshingCatalogue ||
                    !getConnectionId(connection)
                  }
                >
                  {refreshingCatalogue
                    ? 'Refreshing NetSuite Fields...'
                    : 'Refresh NetSuite Fields'}
                </Button>
              )}

              <Button
                type="button"
                onClick={startNewTemplate}
              >
                + New Template
              </Button>
            </div>
          )}
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {message && (
          <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {message}
          </div>
        )}

        {!isDetailPage ? (
          <Card className="p-4 sm:p-6">
            <div className="mb-4">
              <h2 className="text-base font-semibold text-[var(--color-ink)]">Templates</h2>
              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {templates.length} saved template{templates.length === 1 ? '' : 's'}
              </p>
            </div>

            {templates.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted)]">
                No templates created yet.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
                <table className="w-full min-w-[760px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] bg-[var(--color-canvas)] text-left">
                      <th scope="col" className="w-20 px-4 py-3 font-semibold text-[var(--color-ink)]">S. No.</th>
                      <th scope="col" className="px-4 py-3 font-semibold text-[var(--color-ink)]">Name</th>
                      <th scope="col" className="px-4 py-3 font-semibold text-[var(--color-ink)]">Created By</th>
                      <th scope="col" className="px-4 py-3 font-semibold text-[var(--color-ink)]">Created At</th>
                      <th scope="col" className="w-40 px-4 py-3 text-right font-semibold text-[var(--color-ink)]">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((template, index) => (
                      <tr
                        key={template.id}
                        className="border-b border-[var(--color-border)] last:border-b-0 transition-colors hover:bg-[var(--color-canvas)]/60"
                      >
                        <td className="px-4 py-4 text-[var(--color-muted)]">{index + 1}</td>
                        <td className="px-4 py-4">
                          <button
                            type="button"
                            onClick={() => openTemplate(template, 'view')}
                            className="font-medium text-[var(--color-ink)] text-left hover:text-[var(--color-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] rounded-sm"
                            title={`View ${template.name}`}
                          >
                            {template.name || 'Untitled template'}
                          </button>
                        </td>
                        <td className="px-4 py-4 text-[var(--color-ink)]">{getCreatedBy(template)}</td>
                        <td className="px-4 py-4 whitespace-nowrap text-[var(--color-muted)]">
                          {template.created_at ? formatDateTime(template.created_at) : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-3 sm:gap-4">
                            <button
                              type="button"
                              title="View template"
                              aria-label={`View ${template.name}`}
                              onClick={() => openTemplate(template, 'view')}
                              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-[var(--color-ink)] transition hover:bg-[var(--color-surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
                            >
                              <ActionIcon name="view" />
                            </button>
                            <button
                              type="button"
                              title={
                                template.is_preferred
                                  ? 'Preferred template'
                                  : 'Set as preferred'
                              }
                              aria-label={
                                template.is_preferred
                                  ? `${template.name} is your preferred template`
                                  : `Set ${template.name} as preferred`
                              }
                              disabled={template.is_preferred}
                              onClick={() => handleSetPreferred(template)}
                              className="inline-flex h-9 items-center justify-center rounded-md px-2 text-sm font-medium text-[var(--color-primary)] transition hover:bg-[var(--color-canvas)] disabled:cursor-default disabled:opacity-100"
                            >
                              {template.is_preferred
                                ? '★ Preferred'
                                : '☆ Preferred'}
                            </button>
                            <button
                              type="button"
                              title="Edit template"
                              aria-label={`Edit ${template.name}`}
                              onClick={() => openTemplate(template, 'edit')}
                              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-[var(--color-ink)] transition hover:bg-[var(--color-surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
                            >
                              <ActionIcon name="edit" />
                            </button>
                            <button
                              type="button"
                              title="Delete template"
                              aria-label={`Delete ${template.name}`}
                              disabled={deleting}
                              onClick={() => handleDeleteTemplate(template)}
                              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-red-600 transition hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:opacity-50"
                            >
                              <ActionIcon name="delete" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        ) : (
          <div className="min-w-0">
            {mode === 'empty' ? (
              <Card className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-canvas)] text-[var(--color-muted)]">
                  <ActionIcon name="file" className="h-6 w-6" />
                </span>
                <h2 className="text-base font-semibold text-[var(--color-ink)]">Loading template</h2>
                <p className="mt-2 max-w-md text-sm text-[var(--color-muted)]">
                  Please wait while the template details are loaded.
                </p>
              </Card>
            ) : (
              <Card className="min-w-0 p-4 sm:p-6">
                <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                      {mode === 'view' ? 'Template details' : mode === 'new' ? 'New template' : 'Edit template'}
                    </p>
                    {mode === 'view' ? (
                      <h2 className="break-words text-xl font-semibold text-[var(--color-ink)]">
                        {templateName}
                      </h2>
                    ) : (
                      <div>
                        <label htmlFor="template-name" className="block text-sm font-medium text-[var(--color-ink)]">
                          Template Name
                        </label>
                        <input
                          id="template-name"
                          type="text"
                          value={templateName}
                          onChange={(event) => setTemplateName(event.target.value)}
                          placeholder="e.g. Vendor Invoice"
                          className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20"
                          maxLength={150}
                        />
                      </div>
                    )}
                  </div>
                  {mode === 'view' && (
                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        type="button"
                        intent="secondary"
                        onClick={() => {
                          const selected = templates.find((item) => String(item.id) === String(selectedTemplateId))
                          if (selected) selectTemplate(selected, 'edit')
                        }}
                      >
                        Edit
                      </Button>
                      <button
                        type="button"
                        title="Delete template"
                        aria-label="Delete template"
                        disabled={deleting}
                        onClick={() => handleDeleteTemplate(templates.find((item) => String(item.id) === String(selectedTemplateId)))}
                        className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-red-200 text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                      >
                        <ActionIcon name="delete" />
                      </button>
                    </div>
                  )}
                </div>

                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-[var(--color-ink)]">Fields</h3>
                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                      Standard and custom fields can be edited or temporarily disabled. Disabled fields remain visible and can be restored with Use.
                    </p>
                  </div>
                  {mode !== 'view' && (
                    <Button type="button" intent="secondary" size="sm" onClick={addCustomField}>
                      + Add Field
                    </Button>
                  )}
                </div>

                <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
                  <table className="min-w-[1200px] w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-[var(--color-border)] bg-[var(--color-canvas)] text-left">
                        <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">Field Name</th>
                        <th className="min-w-[220px] px-4 py-3 font-semibold text-[var(--color-ink)]">NetSuite Field ID</th>
                        <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">Questionaire</th>
                        <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">Datatype</th>
                        <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">Scope</th>
                        <th className="w-24 px-4 py-3 text-right font-semibold text-[var(--color-ink)]">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fields.map((field) => {
                        const disabledField = field.enabled === false
                        return (
                          <tr
                            id={`template-field-${field.id}`}
                            key={field.id}
                            className={`border-b border-[var(--color-border)] align-top transition-colors ${
                              disabledField
                                ? 'bg-gray-100/80 text-gray-400'
                                : highlightedFieldId === field.id
                                  ? 'bg-amber-50 ring-2 ring-inset ring-amber-300'
                                  : ''
                            }`}
                          >
                            <td className="px-4 py-3">
                              {mode === 'view' || disabledField ? (
                                <div className={`rounded-md border border-transparent px-3 py-2 ${disabledField ? 'text-gray-400' : 'text-[var(--color-ink)]'}`}>
                                  {field.label || 'Unnamed field'}
                                </div>
                              ) : (
                                <input
                                  type="text"
                                  value={field.label}
                                  onChange={(event) => updateField(field.id, {
                                    label: event.target.value,
                                    ...(!field.standard ? {
                                      key: field.key || event.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''),
                                    } : {}),
                                  })}
                                  placeholder="Field name"
                                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                                />
                              )}
                              {/* Key intentionally hidden from UI */}
                            </td>
                            <td className="px-4 py-3">
                              {mode === 'view' || disabledField ? (
                                <div
                                  className={`px-3 py-2 ${
                                    disabledField
                                      ? 'text-gray-400'
                                      : 'text-[var(--color-ink)]'
                                  }`}
                                >
                                  {field.netsuite_field_id || '—'}
                                </div>
                              ) : (
                                <NetSuiteFieldCombobox
                                  loading={netSuiteFieldsLoading}
                                  value={
                                    field.netsuite_field_id
                                      ? `${field.netsuite_field_id}:${field.netsuite_field_scope || ''}:${field.netsuite_field_sublist_id || ''}`
                                      : ''
                                  }
                                  options={sortedNetSuiteFields}
                                  onChange={({ fieldId, scope, sublistId }) =>
                                    updateField(field.id, {
                                      netsuite_field_id: fieldId,
                                      netsuite_field_scope: scope,
                                      netsuite_field_sublist_id: sublistId,
                                    })
                                  }
                                />
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {mode === 'view' || disabledField ? (
                                <div className={`min-h-10 rounded-md px-3 py-2 ${disabledField ? 'text-gray-400' : 'text-[var(--color-ink)]'}`}>
                                  {field.description || '—'}
                                </div>
                              ) : (
                                <textarea
                                  value={field.description}
                                  onChange={(event) => updateField(field.id, { description: event.target.value })}
                                  placeholder="What should AI extract?"
                                  rows={2}
                                  className="w-full resize-y rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                                />
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {mode === 'view' || disabledField ? (
                                <div className={`px-3 py-2 ${disabledField ? 'text-gray-400' : 'text-[var(--color-ink)]'}`}>
                                  {DATA_TYPE_OPTIONS.find((option) => option.value === field.data_type)?.label || field.data_type}
                                </div>
                              ) : (
                                <select
                                  value={field.data_type}
                                  onChange={(event) => updateField(field.id, { data_type: event.target.value })}
                                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                                >
                                  {DATA_TYPE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {mode === 'view' || disabledField ? (
                                <div className={`px-3 py-2 ${disabledField ? 'text-gray-400' : 'text-[var(--color-ink)]'}`}>
                                  {SCOPE_OPTIONS.find((option) => option.value === field.scope)?.label || field.scope}
                                </div>
                              ) : (
                                <select
                                  value={field.scope}
                                  onChange={(event) => updateField(field.id, { scope: event.target.value,netsuite_field_id: '' })}
                                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                                >
                                  {SCOPE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {mode !== 'view' ? (
                                <button
                                  type="button"
                                  onClick={() => toggleField(field.id)}
                                  className={`whitespace-nowrap text-xs font-medium ${
                                    disabledField ? 'text-emerald-700 hover:text-emerald-800' : 'text-[var(--color-muted)] hover:text-red-600'
                                  }`}
                                >
                                  {disabledField ? 'Use' : 'Remove'}
                                </button>
                              ) : (
                                <span className={`text-xs ${disabledField ? 'text-gray-400' : 'text-[var(--color-muted)]'}`}>
                                  {disabledField ? 'Disabled' : '—'}
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                      {fields.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">
                            No fields configured. Click Add Field to create one.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {mode !== 'view' && (
                  <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={() => {
                        if (selectedTemplateId) {
                          const selected = templates.find((item) => String(item.id) === String(selectedTemplateId))
                          if (selected) selectTemplate(selected, 'view')
                          else handleBackToTemplates()
                        } else {
                          handleBackToTemplates()
                        }
                        setError('')
                        setMessage('')
                      }}
                      disabled={saving || deleting}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={() => handleSave({ saveAs: true })}
                      disabled={saving || deleting}
                    >
                      {saving ? 'Saving...' : 'Save As'}
                    </Button>
                    <Button
                      type="button"
                      onClick={() => handleSave()}
                      disabled={saving || deleting}
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </Button>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}
      </div>
    </ClientLayout>
  )
}
