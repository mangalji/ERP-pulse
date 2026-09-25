import { useEffect, useMemo, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import apiClient from '../../services/apiClient.js'

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
    standard: true,
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
    standard: false,
  }
}

function normalizeTemplateConfig(config) {
  if (!config || typeof config !== 'object') {
    return {
      standard_fields: [],
      standard_field_overrides: {},
      custom_fields: [],
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
  }
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

export default function FileTemplatePage() {
  const [catalog, setCatalog] = useState(null)
  const [templates, setTemplates] = useState([])

  const [selectedTemplateId, setSelectedTemplateId] = useState(null)
  const [templateName, setTemplateName] = useState('')

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
      const [catalogData] = await Promise.all([
        loadCatalog(),
        loadTemplates(),
      ])

      const initialFields = [
        ...(Array.isArray(catalogData?.header_fields)
          ? catalogData.header_fields
          : []),
        ...(Array.isArray(catalogData?.line_fields)
          ? catalogData.line_fields
          : []),
      ].map(normalizeCatalogField)

      setFields(initialFields)
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

  const createDefaultFields = () =>
    catalogFields.map(normalizeCatalogField)

  const resetEditor = () => {
    setSelectedTemplateId(null)
    setTemplateName('')
    setFields(createDefaultFields())
    setMessage('')
    setError('')
  }

  const selectTemplate = (template) => {
    const config = normalizeTemplateConfig(template?.fields_config)

    const selectedStandardKeys = new Set(
      config.standard_fields,
    )

    const standardFields = catalogFields
      .filter((field) =>
        selectedStandardKeys.has(field?.key),
      )
      .map((field) => {
        const normalized = normalizeCatalogField(field)
        const override =
          config.standard_field_overrides?.[
            normalized.original_key
          ]

        if (!override || typeof override !== 'object') {
          return normalized
        }

        return {
          ...normalized,
          label:
            override.label ||
            normalized.label,
          description:
            override.description ||
            override.questionaire ||
            normalized.description,
          data_type:
            override.data_type ||
            normalized.data_type,
          scope:
            override.scope === 'line'
              ? 'line'
              : override.scope === 'header'
                ? 'header'
                : normalized.scope,
        }
      })

    const customFields = config.custom_fields.map(
      (field, index) =>
        normalizeCustomField(field, index),
    )

    setSelectedTemplateId(template?.id || null)
    setTemplateName(template?.name || '')
    setFields([...standardFields, ...customFields])
    setMessage('')
    setError('')
  }

  const addCustomField = () => {
    setFields((current) => [
      ...current,
      {
        id: createFieldId('custom'),
        key: '',
        original_key: null,
        label: '',
        description: '',
        data_type: 'text',
        scope: 'header',
        standard: false,
      },
    ])

    setMessage('')
    setError('')
  }

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

  const removeField = (id) => {
    setFields((current) =>
      current.filter((field) => field.id !== id),
    )

    setMessage('')
    setError('')
  }

  const buildFieldsConfig = () => {
    const standardFields = fields
      .filter((field) => field.standard)
      .map(
        (field) =>
          field.original_key ||
          field.key?.trim(),
      )
      .filter(Boolean)

    const standardFieldOverrides = {}

    fields
      .filter((field) => field.standard)
      .forEach((field) => {
        const key =
          field.original_key ||
          field.key?.trim()

        if (!key) return

        standardFieldOverrides[key] = {
          label: field.label?.trim(),
          description: field.description?.trim(),
          questionaire: field.description?.trim(),
          data_type: field.data_type,
          scope: field.scope,
        }
      })

    const customFields = fields
      .filter((field) => !field.standard)
      .map((field) => ({
        key:
          field.key?.trim() ||
          field.label?.trim(),
        label: field.label?.trim(),
        description: field.description?.trim(),
        questionaire: field.description?.trim(),
        data_type: field.data_type,
        scope: field.scope,
      }))

    return {
      standard_fields: standardFields,
      standard_field_overrides: standardFieldOverrides,
      custom_fields: customFields,
    }
  }

  const validateBeforeSave = () => {
    if (!templateName.trim()) {
      return 'Template name is required.'
    }

    const seenKeys = new Set()

    for (const field of fields) {
      const label = field.label?.trim()

      if (!label) {
        return 'Every field must have a Field Name.'
      }

      if (!field.description?.trim()) {
        return `Questionaire is required for "${label}".`
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

  const handleSave = async () => {
    setError('')
    setMessage('')

    const validationError = validateBeforeSave()

    if (validationError) {
      setError(validationError)
      return
    }

    setSaving(true)

    try {
      const payload = {
        name: templateName.trim(),
        fields_config: buildFieldsConfig(),
      }

      let response

      if (selectedTemplateId) {
        response = await apiClient.patch(
          `/ocr/extraction-templates/${selectedTemplateId}/`,
          payload,
        )
      } else {
        response = await apiClient.post(
          '/ocr/extraction-templates/',
          payload,
        )
      }

      const saved =
        response?.data?.data ??
        response?.data ??
        {}

      await loadTemplates()

      if (saved?.id) {
        setSelectedTemplateId(saved.id)
      }

      setMessage(
        selectedTemplateId
          ? 'Template updated successfully.'
          : 'Template created successfully.',
      )
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to save the template.',
        ),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedTemplateId) return

    const confirmed = window.confirm(
      `Delete "${templateName}" template? This action cannot be undone.`,
    )

    if (!confirmed) return

    setDeleting(true)
    setError('')
    setMessage('')

    try {
      await apiClient.delete(
        `/ocr/extraction-templates/${selectedTemplateId}/`,
      )

      await loadTemplates()
      resetEditor()

      setMessage('Template deleted successfully.')
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          'Unable to delete the template.',
        ),
      )
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
        <div>
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            File Templates
          </h1>

          <p className="mt-1 text-sm text-[var(--color-muted)]">
            Create reusable OCR extraction templates and define the
            fields that should be extracted from uploaded documents.
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {message && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {message}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-ink)]">
                  Templates
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  {templates.length} saved template
                  {templates.length === 1 ? '' : 's'}
                </p>
              </div>

              <Button
                type="button"
                intent="secondary"
                size="sm"
                onClick={resetEditor}
              >
                New
              </Button>
            </div>

            {templates.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-muted)]">
                No templates created yet.
              </div>
            ) : (
              <div className="space-y-2">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => selectTemplate(template)}
                    className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                      selectedTemplateId === template.id
                        ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                        : 'border-[var(--color-border)] hover:bg-[var(--color-canvas)]'
                    }`}
                  >
                    <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                      {template.name}
                    </p>

                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                      Created{' '}
                      {template.created_at
                        ? new Date(
                            template.created_at,
                          ).toLocaleDateString()
                        : '—'}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <div className="mb-6">
              <label className="block text-sm font-medium text-[var(--color-ink)]">
                Template Name
              </label>

              <input
                type="text"
                value={templateName}
                onChange={(event) =>
                  setTemplateName(event.target.value)
                }
                placeholder="e.g. Vendor Invoice"
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20"
                maxLength={150}
              />
            </div>

            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-ink)]">
                  Fields
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Standard and custom fields can be edited or removed.
                  The original key of a standard field is preserved for
                  the existing OCR extraction contract.
                </p>
              </div>

              <Button
                type="button"
                intent="secondary"
                size="sm"
                onClick={addCustomField}
              >
                + Add Field
              </Button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
              <table className="min-w-[980px] w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-canvas)] text-left">
                    <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">
                      Field Name
                    </th>

                    <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">
                      Questionaire
                    </th>

                    <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">
                      Datatype
                    </th>

                    <th className="px-4 py-3 font-semibold text-[var(--color-ink)]">
                      Scope
                    </th>

                    <th className="w-24 px-4 py-3 text-right font-semibold text-[var(--color-ink)]">
                      Action
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {fields.map((field) => (
                    <tr
                      key={field.id}
                      className="border-b border-[var(--color-border)] align-top"
                    >
                      <td className="px-4 py-3">
                        <input
                          type="text"
                          value={field.label}
                          onChange={(event) =>
                            updateField(field.id, {
                              label: event.target.value,
                              ...(!field.standard
                                ? {
                                    key:
                                      field.key ||
                                      event.target.value
                                        .toLowerCase()
                                        .replace(
                                          /[^a-z0-9]+/g,
                                          '_',
                                        )
                                        .replace(
                                          /^_+|_+$/g,
                                          '',
                                        ),
                                  }
                                : {}),
                            })
                          }
                          placeholder="Field name"
                          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                        />

                        {field.standard && (
                          <p className="mt-1 text-xs text-[var(--color-muted)]">
                            Key: {field.original_key}
                          </p>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        <textarea
                          value={field.description}
                          onChange={(event) =>
                            updateField(field.id, {
                              description:
                                event.target.value,
                            })
                          }
                          placeholder="What should AI extract?"
                          rows={2}
                          className="w-full resize-y rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                        />
                      </td>

                      <td className="px-4 py-3">
                        <select
                          value={field.data_type}
                          onChange={(event) =>
                            updateField(field.id, {
                              data_type:
                                event.target.value,
                            })
                          }
                          className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                        >
                          {DATA_TYPE_OPTIONS.map(
                            (option) => (
                              <option
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </option>
                            ),
                          )}
                        </select>
                      </td>

                      <td className="px-4 py-3">
                        <select
                          value={field.scope}
                          onChange={(event) =>
                            updateField(field.id, {
                              scope:
                                event.target.value,
                            })
                          }
                          className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
                        >
                          {SCOPE_OPTIONS.map(
                            (option) => (
                              <option
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </option>
                            ),
                          )}
                        </select>
                      </td>

                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() =>
                            removeField(field.id)
                          }
                          className="text-xs font-medium text-red-600 hover:text-red-700"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}

                  {fields.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-4 py-8 text-center text-sm text-[var(--color-muted)]"
                      >
                        No fields configured.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
              {selectedTemplateId && (
                <Button
                  type="button"
                  intent="secondary"
                  onClick={handleDelete}
                  disabled={deleting || saving}
                >
                  {deleting
                    ? 'Deleting...'
                    : 'Delete Template'}
                </Button>
              )}

              <Button
                type="button"
                onClick={handleSave}
                disabled={saving || deleting}
              >
                {saving
                  ? 'Saving...'
                  : selectedTemplateId
                    ? 'Update Template'
                    : 'Save Template'}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </ClientLayout>
  )
}
