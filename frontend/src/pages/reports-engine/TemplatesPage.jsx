import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import TemplateCard from '../../components/reports-engine/TemplateCard.jsx'
import { REPORT_TYPES } from '../../components/reports-engine/constants.js'
import { reportsEngineApi } from '../../services/reportsEngine.js'

/**
 * Templates page. Lists saved report templates with create / edit /
 * delete / quick generate.
 */
export default function TemplatesPage() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [name, setName] = useState('')
  const [reportType, setReportType] = useState('SALES')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await reportsEngineApi.templates.list({ limit: 100, offset: 0 })
      setTemplates(res?.results ?? res ?? [])
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load templates')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const openCreate = () => {
    setEditing(null)
    setName('')
    setReportType('SALES')
    setCreateOpen(true)
  }

  const openEdit = (template) => {
    setEditing(template)
    setName(template.name)
    setReportType(template.report_type)
    setCreateOpen(true)
  }

  const handleSave = async () => {
    if (!name.trim()) return
    const payload = {
      name,
      report_type: reportType,
      config: { preset: 'last_30_days' },
    }
    try {
      if (editing) {
        await reportsEngineApi.templates.update(editing.id, payload)
      } else {
        await reportsEngineApi.templates.create(payload)
      }
      setCreateOpen(false)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to save template')
    }
  }

  const handleDelete = async (template) => {
    if (!window.confirm(`Delete template "${template.name}"?`)) return
    try {
      await reportsEngineApi.templates.remove(template.id)
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to delete template')
    }
  }

  const handleGenerate = (template) => {
    navigate(`/app/reports-engine/generate?type=${template.report_type}`)
  }

  const selectClass =
    'rounded-lg border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none transition-colors focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]'

  return (
    <ClientLayout title="Reports" breadcrumb="Templates">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Report Templates
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Save reusable report configurations for quick generation.
            </p>
          </div>
          <Button onClick={openCreate}>New Template</Button>
        </div>

        {error && (
          <div className="rounded-lg border border-[var(--color-negative)] bg-[var(--color-negative-soft)] px-4 py-3 text-sm text-[var(--color-negative)]">
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        ) : templates.length === 0 ? (
          <Card className="p-5">
            <EmptyState
              title="No templates yet"
              description="Save a template to quickly regenerate reports with the same filters."
              actionLabel="New Template"
              action={openCreate}
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                onGenerate={handleGenerate}
                onEdit={openEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}

        {createOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button aria-label="Close" onClick={() => setCreateOpen(false)} className="absolute inset-0 bg-black/40" />
            <div className="relative w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <h3 className="mb-4 font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                {editing ? 'Edit Template' : 'New Template'}
              </h3>
              <div className="flex flex-col gap-4">
                <Input
                  label="Template Name"
                  id="template-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Monthly sales report"
                />
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-[var(--color-ink-soft)]">Report Type</span>
                  <select className={selectClass} value={reportType} onChange={(e) => setReportType(e.target.value)}>
                    {REPORT_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button intent="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
                <Button onClick={handleSave} disabled={!name.trim()}>
                  {editing ? 'Save' : 'Create'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ClientLayout>
  )
}
