export const TOP_LEVEL_FIELDS = [
  { key: 'invoice_number', label: 'Invoice Number', type: 'text' },
  { key: 'invoice_date', label: 'Invoice Date', type: 'date' },
  { key: 'due_date', label: 'Due Date', type: 'date' },
  { key: 'vendor_name', label: 'Vendor Name', type: 'text' },
  { key: 'subsidiary', label: 'Subsidiary', type: 'text' },
  { key: 'currency', label: 'Currency', type: 'text' },
  { key: 'location', label: 'Location', type: 'text' },
  // Temporarily disabled: header-level total tax is NetSuite-computed.
  // { key: 'total_tax_amount', label: 'Total Tax', type: 'currency' },
  { key: 'amount', label: 'Amount', type: 'currency' },
]

export const LINE_ITEM_FIELDS = [
  { key: 'item', label: 'Item / account/ description', type: 'text' },
  { key: 'quantity', label: 'Qty', type: 'number' },
  { key: 'unit_price', label: 'Unit Price', type: 'currency' },
  { key: 'subtotal', label: 'Subtotal', type: 'currency' },
  { key: 'tax_amount', label: 'Tax Amount', type: 'currency' },
  { key: 'tax_rate', label: 'Tax Rate (%)', type: 'number' },
  { key: 'total_amount', label: 'Total Amount', type: 'currency' },
]

export const DEFAULT_FIELD_DEFINITIONS = [
  ...TOP_LEVEL_FIELDS.map((field) => ({ ...field, scope: 'header', dataType: field.type })),
  ...LINE_ITEM_FIELDS.map((field) => ({ ...field, scope: 'line', dataType: field.type })),
]

export function slugifyFieldKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'custom_field'
}

export function toInputType(dataType) {
  if (dataType === 'number' || dataType === 'currency') return 'number'
  if (dataType === 'date') return 'date'
  return 'text'
}

export function numericValue(value) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(parsed) ? parsed : null
}

export function money(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

export function recalculateInvoiceTotals(current, fields = null) {
  const items = Array.isArray(current?.line_items) ? current.line_items : []
  // Temporarily disabled with the header-level total tax field.
  // const headerDefaults = new Map((fields?.headerFields || [])
  //   .filter((field) => field.defaultValue !== null && field.defaultValue !== undefined && field.defaultValue !== '')
  //   .map((field) => [field.key, field.defaultValue]))
  const lineDefaults = new Map((fields?.lineFields || [])
    .filter((field) => field.defaultValue !== null && field.defaultValue !== undefined && field.defaultValue !== '')
    .map((field) => [field.key, field.defaultValue]))

  // Header-level total tax is intentionally not calculated.
  // let totalTax = 0
  let invoiceTotal = 0
  const lineItems = items.map((item) => {
    const quantity = numericValue(item?.quantity)
    const unitPrice = numericValue(item?.unit_price)
    const subtotal = quantity !== null && unitPrice !== null
      ? money(quantity * unitPrice)
      : numericValue(item?.subtotal)
    const taxRate = numericValue(item?.tax_rate)
    const taxAmount = taxRate !== null && subtotal !== null
      ? money(subtotal * taxRate / 100)
      : numericValue(item?.tax_amount)
    const effectiveSubtotal = numericValue(lineDefaults.get('subtotal')) ?? subtotal
    const effectiveTaxAmount = numericValue(lineDefaults.get('tax_amount')) ?? taxAmount
    const totalAmount = effectiveSubtotal !== null
      ? money(effectiveSubtotal + (effectiveTaxAmount ?? 0))
      : numericValue(item?.total_amount)

    // totalTax += effectiveTaxAmount ?? 0
    invoiceTotal += numericValue(lineDefaults.get('total_amount')) ?? totalAmount ?? 0
    return {
      ...item,
      subtotal: lineDefaults.get('subtotal') ?? subtotal,
      tax_amount: lineDefaults.get('tax_amount') ?? taxAmount,
      total_amount: lineDefaults.get('total_amount') ?? totalAmount,
    }
  })

  return {
    ...current,
    line_items: lineItems,
    // total_tax_amount: headerDefaults.get('total_tax_amount') ?? money(totalTax),
    amount: headerDefaults.get('amount') ?? money(invoiceTotal),
  }
}

export function resolveConfiguredFields(config, fallbackData = {}) {
  const hasTemplateConfig = config && typeof config === 'object' && (
    Array.isArray(config.standard_fields) || Array.isArray(config.custom_fields)
  )
  let headerFields = []
  let lineFields = []

  if (hasTemplateConfig) {
    const overrides = config.standard_field_overrides && typeof config.standard_field_overrides === 'object'
      ? config.standard_field_overrides
      : {}
    const standardFields = (Array.isArray(config.standard_fields) ? config.standard_fields : [])
      .map((rawKey) => {
        const key = String(rawKey || '').trim()
        if (!key || key === 'line_items' || key === 'customer_name') return null
        const base = DEFAULT_FIELD_DEFINITIONS.find((field) => field.key === key)
        const override = overrides[key] && typeof overrides[key] === 'object' ? overrides[key] : {}
        if (!base || override.enabled === false) return null
        const dataType = override.data_type || base.dataType || base.type || 'text'
        const scope = override.scope === 'line' || override.scope === 'header' ? override.scope : base.scope
        return {
          ...base,
          key,
          label: String(override.label || base.label || key),
          description: String(override.questionaire || override.description || base.description || ''),
          dataType,
          type: toInputType(dataType),
          scope,
          defaultValue: override.default_value ?? null,
          standard: true,
        }
      })
      .filter(Boolean)
    const customFields = (Array.isArray(config.custom_fields) ? config.custom_fields : [])
      .filter((field) => field && field.enabled !== false)
      .map((field) => {
        const rawKey = field.key || field.label
        const key = slugifyFieldKey(rawKey)
        const dataType = field.data_type || 'text'
        return {
          key,
          label: String(field.label || rawKey || key),
          description: String(field.questionaire || field.description || ''),
          dataType,
          type: toInputType(dataType),
          scope: field.scope === 'line' ? 'line' : 'header',
          defaultValue: field.default_value ?? null,
          standard: false,
        }
      })
    const seen = new Set()
    ;[...standardFields, ...customFields].forEach((field) => {
      if (seen.has(field.key)) return
      seen.add(field.key)
      if (field.scope === 'line') lineFields.push(field)
      else headerFields.push(field)
    })
  } else {
    const source = fallbackData && typeof fallbackData === 'object' ? fallbackData : {}
    const defaultByKey = new Map(DEFAULT_FIELD_DEFINITIONS.map((field) => [field.key, field]))
    Object.keys(source).forEach((key) => {
      if (key === 'line_items' || key === 'customer_name') return
      const base = defaultByKey.get(key)
      const dataType = base?.dataType || 'text'
      headerFields.push({ key, label: base?.label || key, dataType, type: toInputType(dataType), scope: 'header' })
    })
    const seenLineKeys = new Set()
    ;(Array.isArray(source.line_items) ? source.line_items : []).forEach((item) => {
      if (!item || typeof item !== 'object') return
      Object.keys(item).forEach((key) => {
        if (key === 'customer_name' || seenLineKeys.has(key)) return
        seenLineKeys.add(key)
        const base = defaultByKey.get(key)
        const dataType = base?.dataType || 'text'
        lineFields.push({ key, label: base?.label || key, dataType, type: toInputType(dataType), scope: 'line' })
      })
    })
  }

  const typesByKey = {}
  ;[...headerFields, ...lineFields].forEach((field) => { typesByKey[field.key] = field.dataType || 'text' })
  return { headerFields, lineFields, typesByKey, hasTemplateConfig: Boolean(hasTemplateConfig) }
}

export function projectDataToConfiguredFields(data, configuredFields) {
  const source = data && typeof data === 'object' && !Array.isArray(data) ? data : {}
  const projected = {}
  ;(configuredFields?.headerFields || []).forEach((field) => { projected[field.key] = source[field.key] ?? null })
  const lineFields = configuredFields?.lineFields || []
  if (lineFields.length) {
    const items = Array.isArray(source.line_items) ? source.line_items : []
    projected.line_items = items.map((item) => {
      const row = {}
      lineFields.forEach((field) => { row[field.key] = item && typeof item === 'object' ? (item[field.key] ?? null) : null })
      return row
    })
  }
  return projected
}

export function normalizeFieldValue(value, dataType) {
  if (value === '' || value === null || value === undefined) return null
  if (dataType === 'number' || dataType === 'currency') {
    const parsed = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  if (dataType === 'boolean') {
    if (typeof value === 'boolean') return value
    const lowered = String(value).trim().toLowerCase()
    if (['true', 'yes', '1'].includes(lowered)) return true
    if (['false', 'no', '0'].includes(lowered)) return false
    return null
  }
  if (typeof value === 'string') return value.trim() || null
  return value
}

export function emptyLineItem(lineFields = []) {
  return Object.fromEntries(lineFields.map((field) => [field.key, null]))
}

export function cloneData(data) {
  if (!data || typeof data !== 'object') return {}
  let source = Array.isArray(data) ? (data[0] || {}) : data
  if (source && typeof source === 'object' && !Array.isArray(source.data) && source.data && typeof source.data === 'object') {
    source = source.data
  }
  const cloned = JSON.parse(JSON.stringify(source))
  if (cloned && typeof cloned === 'object' && !Array.isArray(cloned)) delete cloned.customer_name
  return cloned
}

export function toInputValue(value) {
  return value === null || value === undefined ? '' : String(value)
}

export function normalizeEditedData(data, configuredFields) {
  const source = cloneData(data)
  const next = {}
  const headerFields = configuredFields?.headerFields || []
  const lineFields = configuredFields?.lineFields || []
  headerFields.forEach((field) => { next[field.key] = normalizeFieldValue(source[field.key], field.dataType || 'text') })
  if (lineFields.length) {
    next.line_items = (Array.isArray(source.line_items) ? source.line_items : []).map((item) => {
      const row = {}
      lineFields.forEach((field) => { row[field.key] = normalizeFieldValue(item?.[field.key], field.dataType || 'text') })
      return row
    })
  }
  return next
}

export function isImage(file) {
  const name = file?.name || file?.filename || ''
  return Boolean(file && (
    String(file.type || '').startsWith('image/') ||
    /\.(png|jpe?g|webp|gif|bmp|tif|tiff)$/i.test(name)
  ))
}

export function isPdf(file) {
  const name = file?.name || file?.filename || ''
  return Boolean(file && (file.type === 'application/pdf' || /\.pdf$/i.test(name)))
}

export function isDocx(file) {
  const name = file?.name || file?.filename || ''
  return Boolean(file && (file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' || /\.docx$/i.test(name)))
}

export function isSpreadsheet(file) {
  const name = String(file?.name || file?.filename || '').toLowerCase()
  return Boolean(file && (
    file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    file.type === 'application/vnd.ms-excel' || name.endsWith('.xlsx') || name.endsWith('.xls')
  ))
}

export function isCsv(file) {
  const name = String(file?.name || file?.filename || '').toLowerCase()
  return Boolean(file && (['text/csv', 'application/csv', 'application/vnd.ms-excel'].includes(file.type) || name.endsWith('.csv')))
}

export function isText(file) {
  const name = String(file?.name || file?.filename || '').toLowerCase()
  return Boolean(file && (file.type === 'text/plain' || name.endsWith('.txt')))
}

export function getFileCategory(file) {
  if (isPdf(file)) return 'PDF'
  if (isDocx(file)) return 'DOCX'
  if (isImage(file)) return 'Image'
  if (isSpreadsheet(file)) return 'Spreadsheet'
  if (isCsv(file)) return 'CSV'
  if (isText(file)) return 'Text'
  return 'Document'
}
