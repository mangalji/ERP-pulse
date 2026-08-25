import { useEffect, useMemo, useState } from 'react'
import apiClient from '../../services/apiClient.js'

const DATA_TYPE_OPTIONS = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'currency', label: 'Currency' },
]

function slugify(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function cx(...classes) {
  return classes.filter(Boolean).join(' ')
}

/**
 * Dynamic extraction configuration panel (Phase 2).
 *
 * Lets the user pick which standard fields to extract, add custom fields
 * with an AI description + header/line scope + datatype, save the
 * configuration as a reusable template, and apply a previously saved
 * template. Emits { requested_fields, template_id } up to the parent, or
 * nulls when the default (full standard set) extraction path should be
 * used.
 */
export default function ExtractionConfigPanel({ onChange }) {
  const [catalog, setCatalog] = useState(null)
  const [catalogError, setCatalogError] = useState('')

  const [expanded, setExpanded] = useState(true)
  const [standardSelected, setStandardSelected] = useState({})
  const [lineItemsEnabled, setLineItemsEnabled] = useState(true)
  const [confirmedCustomFields, setConfirmedCustomFields] = useState([])
  const [draft, setDraft] = useState(null) // null | {label, description, scope, data_type}

  const [templates, setTemplates] = useState([])
  const [selectedTemplateId, setSelectedTemplateId] = useState(null)
  const [templateName, setTemplateName] = useState('')
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [templateMsg, setTemplateMsg] = useState('')
  const [templateError, setTemplateError] = useState('')

  const fetchCatalog = async () => {
    try {
      const response = await apiClient.get('/ocr/extraction-fields/')
      const data = response?.data?.data ?? response?.data ?? {}
      setCatalog(data)
      const initial = {}
      ;(data?.header_fields || []).forEach((f) => {
        initial[f.key] = true
      })
      setStandardSelected(initial)
    } catch (err) {
      setCatalogError(
        err?.response?.data?.detail ||
          err?.message ||
          'Unable to load extraction field catalogue.',
      )
    }
  }

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/ocr/extraction-templates/')
      const data = response?.data?.data ?? response?.data ?? []
      setTemplates(Array.isArray(data) ? data : [])
    } catch (err) {
      // Non-fatal: the user can still configure manually.
      console.error('Failed to load extraction templates:', err)
    }
  }

  // Load the catalogue once for the current configuration panel.
  useEffect(() => {
    if (!catalog && !catalogError) {
      fetchCatalog()
      fetchTemplates()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const headerFields = useMemo(
    () => catalog?.header_fields || [],
    [catalog],
  )

  const buildRequested = () => {
    const standard = []
    headerFields.forEach((f) => {
      if (standardSelected[f.key]) standard.push(f.key)
    })
    if (lineItemsEnabled) standard.push('line_items')

    const custom = confirmedCustomFields
      .filter((cf) => cf.label && cf.label.trim())
      .map((cf) => ({
        key: slugify(cf.label),
        label: cf.label.trim(),
        description: (cf.description || '').trim(),
        scope: cf.scope === 'line' && !lineItemsEnabled ? 'header' : cf.scope,
        data_type: cf.data_type || 'text',
      }))

    return { standard_fields: standard, custom_fields: custom }
  }

  // Emit the current configuration up to the parent.
  // Collapsing the UI is visual only; it must never disable the selected
  // extraction fields.
  useEffect(() => {
    onChange?.({
      requested_fields: buildRequested(),
      template_id: selectedTemplateId,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [standardSelected, lineItemsEnabled, confirmedCustomFields, selectedTemplateId])

  const toggleStandard = (key) => {
    setStandardSelected((current) => ({ ...current, [key]: !current[key] }))
  }

  const handleLineItemsToggle = (next) => {
    setLineItemsEnabled(next)
    if (!next) {
      // Enforce Phase 2 rule: line-scoped custom fields require line_items.
      setConfirmedCustomFields((current) =>
        current.filter((cf) => cf.scope !== 'line'),
      )
      setDraft((current) =>
        current && current.scope === 'line'
          ? { ...current, scope: 'header' }
          : current,
      )
    }
  }

  // --- Custom fields: draft -> confirm -> confirmed list -------------------
  const openDraft = () => {
    setDraft({
      label: '',
      description: '',
      scope: 'header',
      data_type: 'text',
    })
  }

  const updateDraft = (patch) => {
    setDraft((current) => (current ? { ...current, ...patch } : current))
  }

  const cancelDraft = () => setDraft(null)

  const confirmDraft = () => {
    if (!draft || !draft.label.trim()) return
    const field = {
      id: `cf_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      label: draft.label.trim(),
      description: (draft.description || '').trim(),
      scope:
        draft.scope === 'line' && !lineItemsEnabled ? 'header' : draft.scope || 'header',
      data_type: draft.data_type || 'text',
    }
    setConfirmedCustomFields((current) => [...current, field])
    setDraft(null)
  }

  const removeConfirmed = (id) => {
    setConfirmedCustomFields((current) => current.filter((cf) => cf.id !== id))
  }

  const loadTemplate = (id) => {
    setTemplateMsg('')
    setTemplateError('')
    if (!id) {
      setSelectedTemplateId(null)
      return
    }
    const tpl = templates.find((t) => String(t.id) === String(id))
    if (!tpl) {
      setSelectedTemplateId(id)
      return
    }
    const config = tpl.fields_config || {}
    const std = config.standard_fields || []
    const nextSelected = {}
    headerFields.forEach((f) => {
      nextSelected[f.key] = std.includes(f.key)
    })
    const lineOn = std.includes('line_items')
    const customs = (config.custom_fields || [])
      .filter((c) => c && c.label)
      .map((c) => ({
        id: `cf_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        label: c.label,
        description: c.description || '',
        scope: c.scope === 'line' && !lineOn ? 'header' : c.scope || 'header',
        data_type: c.data_type || 'text',
      }))
    setStandardSelected(nextSelected)
    setLineItemsEnabled(lineOn)
    setConfirmedCustomFields(customs)
    setSelectedTemplateId(id)
    setTemplateName(tpl.name || '')
  }

  const saveTemplate = async () => {
    const name = templateName.trim()
    if (!name) {
      setTemplateError('Enter a name to save this configuration as a template.')
      return
    }
    setSavingTemplate(true)
    setTemplateError('')
    setTemplateMsg('')
    try {
      const response = await apiClient.post('/ocr/extraction-templates/', {
        name,
        fields_config: buildRequested(),
      })
      const data = response?.data?.data ?? response?.data ?? {}
      setSelectedTemplateId(data?.id || selectedTemplateId)
      setTemplateMsg('Template saved.')
      await fetchTemplates()
    } catch (err) {
      setTemplateError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to save template.',
      )
    } finally {
      setSavingTemplate(false)
    }
  }

  const labelClass = 'text-sm font-medium text-[var(--color-ink)]'
  const inputClass =
    'w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={labelClass}>Data Extraction Configuration</p>
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            Choose which fields to extract, add custom fields, or reuse a saved
            template.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openDraft}
            disabled={draft !== null}
            className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-ink)] hover:bg-[var(--color-surface)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {confirmedCustomFields.length > 0
              ? '+ Add another custom field'
              : '+ Add custom field'}
          </button>

          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-border)] bg-white text-[var(--color-ink)] transition hover:bg-[var(--color-surface)]"
            aria-expanded={expanded}
            aria-label={
              expanded
                ? 'Collapse extraction configuration'
                : 'Expand extraction configuration'
            }
          >
            <span
              className={`text-xl leading-none transition-transform duration-200 ${
                expanded ? '' : 'rotate-180'
              }`}
            >
              ˅
            </span>
          </button>
        </div>
      </div>

      {!expanded && (
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          Configuration is collapsed. Click ˅ to expand it.
        </p>
      )}

      {expanded && (
        <div className="mt-4 flex flex-col gap-5">
          {catalogError && (
            <p className="text-xs text-red-600">{catalogError}</p>
          )}

          {/* Templates */}
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[220px] flex-1">
              <label className={cx(labelClass, 'block')}>
                Apply saved template
              </label>
              <select
                value={selectedTemplateId || ''}
                onChange={(e) => loadTemplate(e.target.value)}
                className={cx(inputClass, 'mt-1')}
              >
                <option value="">— None / manual —</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-[200px] flex-1">
              <label className={cx(labelClass, 'block')}>
                Save as template
              </label>
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Template name"
                className={cx(inputClass, 'mt-1')}
              />
            </div>

            <button
              type="button"
              onClick={saveTemplate}
              disabled={savingTemplate}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
            >
              {savingTemplate ? 'Saving...' : 'Save Template'}
            </button>
          </div>

          {templateMsg && (
            <p className="text-xs text-emerald-600">{templateMsg}</p>
          )}
          {templateError && (
            <p className="text-xs text-red-600">{templateError}</p>
          )}

          {/* Standard header fields */}
          <div>
            <p className={labelClass}>Standard fields</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {headerFields.map((f) => (
                <label
                  key={f.key}
                  className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)]"
                >
                  <input
                    type="checkbox"
                    checked={!!standardSelected[f.key]}
                    onChange={() => toggleStandard(f.key)}
                    className="h-4 w-4 accent-[var(--color-primary)]"
                  />
                  <span className="flex-1">{f.label}</span>
                  <span className="text-[10px] uppercase tracking-wide text-[var(--color-muted)]">
                    {f.data_type}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Line items toggle */}
          <label className="flex max-w-sm items-center gap-2 text-sm text-[var(--color-ink)]">
            <input
              type="checkbox"
              checked={lineItemsEnabled}
              onChange={(e) => handleLineItemsToggle(e.target.checked)}
              className="h-4 w-4 accent-[var(--color-primary)]"
            />
            Extract line items
          </label>

          {/* Custom fields — shown as additional fields that are part of the extraction config */}
          <div>
            <div className="flex items-center justify-between gap-3">
              <p className={labelClass}>
                Additional custom fields (sent to AI)
              </p>
            </div>

            {!lineItemsEnabled && (
              <p className="mt-2 text-xs text-amber-600">
                Line-item custom fields are disabled because line items
                extraction is off.
              </p>
            )}

            {draft === null && confirmedCustomFields.length === 0 && (
              <p className="mt-2 text-xs text-[var(--color-muted)]">
                No custom fields yet. Add one to instruct the AI to extract
                extra data not in the standard set.
              </p>
            )}

            {/* Confirmed custom fields — styled like standard field tiles
                and shown in the same grid. */}
            {confirmedCustomFields.length > 0 && (
              <div className="mt-3">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {confirmedCustomFields.map((cf) => (
                    <div
                      key={cf.id}
                      className="flex min-w-0 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)]"
                    >
                      <span
                        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px] bg-[var(--color-primary)] text-[10px] font-bold text-white"
                        aria-hidden="true"
                      >
                        ✓
                      </span>

                      <span className="min-w-0 flex-1 truncate font-medium">
                        {cf.label}
                      </span>

                      <span className="shrink-0 text-[10px] uppercase tracking-wide text-[var(--color-muted)]">
                        {cf.data_type}
                      </span>

                      <button
                        type="button"
                        onClick={() => removeConfirmed(cf.id)}
                        className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold text-red-600 hover:bg-red-50"
                        aria-label={`Remove ${cf.label}`}
                        title={
                          cf.description
                            ? cf.description
                            : `Remove ${cf.label}`
                        }
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Draft card — one at a time */}
            {draft !== null && (
              <div className="mt-3 rounded-lg border border-[var(--color-primary)] bg-[var(--color-surface)] p-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="text-xs font-medium text-[var(--color-muted)]">
                      Label
                    </label>
                    <input
                      type="text"
                      value={draft.label}
                      onChange={(e) => updateDraft({ label: e.target.value })}
                      placeholder="e.g. GSTIN"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-[var(--color-muted)]">
                      Datatype
                    </label>
                    <select
                      value={draft.data_type}
                      onChange={(e) =>
                        updateDraft({ data_type: e.target.value })
                      }
                      className={inputClass}
                    >
                      {DATA_TYPE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mt-3">
                  <label className="text-xs font-medium text-[var(--color-muted)]">
                    AI instruction / description
                  </label>
                  <input
                    type="text"
                    value={draft.description}
                    onChange={(e) =>
                      updateDraft({ description: e.target.value })
                    }
                    placeholder="What should the AI look for on the document?"
                    className={inputClass}
                  />
                </div>

                <div className="mt-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-medium text-[var(--color-muted)]">
                      Scope
                    </label>
                    <select
                      value={draft.scope}
                      disabled={!lineItemsEnabled}
                      onChange={(e) => updateDraft({ scope: e.target.value })}
                      className={cx(
                        inputClass,
                        'w-auto',
                        !lineItemsEnabled && 'opacity-50',
                      )}
                    >
                      <option value="header">Header</option>
                      <option value="line" disabled={!lineItemsEnabled}>
                        Line item
                      </option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={cancelDraft}
                      className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-muted)] hover:bg-[var(--color-canvas)]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={confirmDraft}
                      disabled={!draft.label.trim()}
                      className="rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                    >
                      Add Field
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}