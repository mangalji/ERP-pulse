import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

const PAGE_SIZE = 10

export default function ModulesPage() {
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [assignOpen, setAssignOpen] = useState(false)
  const [companies, setCompanies] = useState([])
  const [assignedRows, setAssignedRows] = useState([])
  const [assignCompany, setAssignCompany] = useState('')
  const [assignLoading, setAssignLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  /* Module Edit Modal state (View/Edit) */
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editModule, setEditModule] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', code: '', display_name: '', description: '', is_active: true })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listModules({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load modules')
    } finally {
      setLoading(false)
    }
  }, [search, offset])

  useEffect(() => {
    load()
  }, [load])

  const openAssign = async () => {
    setAssignOpen(true)
    setAssignLoading(true)
    try {
      const compData = await superadminApi.listCompanies({ limit: 100 })
      setCompanies(compData.results || [])
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load companies', 'error')
    } finally {
      setAssignLoading(false)
    }
  }

  const loadCompanyModules = async (companyId) => {
    if (!companyId) {
      setAssignedRows([])
      return
    }
    try {
      const all = await superadminApi.listModules({ limit: 100 })
      const companyModules = await superadminApi.fetchCompanyModules(companyId)
      const enabledMap = {}
      companyModules.forEach((m) => {
        enabledMap[m.module_id] = m.enabled
      })
      setAssignedRows(
        (all.results || []).map((m) => ({
          ...m,
          enabled: enabledMap[m.id] ?? false,
        })),
      )
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load company modules', 'error')
    }
  }

  const toggleAssigned = (id) => {
    setAssignedRows((prev) => prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m)))
  }

  const bulkToggleAssigned = (enabled) => {
    setAssignedRows((prev) => prev.map((m) => ({ ...m, enabled })))
  }

  const saveAssignments = async () => {
    if (!assignCompany) return
    setSaving(true)
    try {
      const enabledIds = assignedRows.filter((m) => m.enabled).map((m) => m.id)
      const disabledIds = assignedRows.filter((m) => !m.enabled).map((m) => m.id)
      if (enabledIds.length) {
        await superadminApi.bulkSetCompanyModules({ company_id: assignCompany, module_ids: enabledIds, enabled: true })
      }
      if (disabledIds.length) {
        await superadminApi.bulkSetCompanyModules({ company_id: assignCompany, module_ids: disabledIds, enabled: false })
      }
      addToast('Company modules updated successfully')
      setAssignOpen(false)
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to save assignments', 'error')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    { key: 'name', header: 'Name', render: (row) => <span className="font-medium text-[var(--color-ink)]">{row.name}</span> },
    { key: 'code', header: 'Code', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.code}</span> },
    { key: 'display_name', header: 'Display Name', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.display_name || '—'}</span> },
    { key: 'description', header: 'Description', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.description || '—'}</span> },
    { key: 'is_active', header: 'Status', render: (row) => <StatusBadge status={row.is_active} /> },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => { setEditModule(row); setEditForm({ name: row.name, code: row.code, display_name: row.display_name || '', description: row.description || '', is_active: row.is_active }); setEditModalOpen(true) }}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
          >
            View
          </button>
        </div>
      ),
    },
  ]

  return (
    <AdminLayout title="Modules" breadcrumb="Modules">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Dashboard</span>
        </div>
        <PageHeader
          title="Modules"
          subtitle="View feature modules and manage per-company assignments."
          actions={
            <Button onClick={openAssign}>Company Module Assignment</Button>
          }
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setOffset(0) }} placeholder="Search modules..." />
            <span className="text-xs text-[var(--color-muted)]">{count} module{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No modules found"
            emptyDescription="No modules match your search."
          />

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <span className="text-sm text-[var(--color-muted)]">Page {currentPage} of {totalPages}</span>
              <Button intent="secondary" size="sm" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          )}
        </Card>
      </div>

      {/* Company Module Assignment Modal */}
      {assignOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setAssignOpen(false)} />
          <div className="relative flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              Company Module Assignment
            </h3>

            <label className="mt-4 flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[var(--color-ink-soft)]">Select Company</span>
              <select
                value={assignCompany}
                onChange={(e) => { setAssignCompany(e.target.value); loadCompanyModules(e.target.value) }}
                className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
              >
                <option value="">Select a company...</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>

            <div className="mt-4 flex items-center justify-between">
              <div className="flex gap-2">
                <Button intent="secondary" size="sm" onClick={() => bulkToggleAssigned(true)}>Enable All</Button>
                <Button intent="secondary" size="sm" onClick={() => bulkToggleAssigned(false)}>Disable All</Button>
              </div>
            </div>

            <div className="mt-4 flex-1 overflow-y-auto rounded-lg border border-[var(--color-border)]">
              {assignLoading ? (
                <p className="p-6 text-center text-sm text-[var(--color-muted)]">Loading...</p>
              ) : assignedRows.length === 0 ? (
                <p className="p-6 text-center text-sm text-[var(--color-muted)]">Select a company to view module assignments.</p>
              ) : (
                <div className="flex flex-col">
                  {assignedRows.map((m) => (
                    <label key={m.id} className="flex cursor-pointer items-center justify-between border-b border-[var(--color-border)] px-4 py-3 last:border-0 hover:bg-[var(--color-canvas)]">
                      <div>
                        <p className="text-sm font-medium text-[var(--color-ink)]">{m.name}</p>
                        <p className="text-xs text-[var(--color-muted)]">{m.code}</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={m.enabled}
                        onChange={() => toggleAssigned(m.id)}
                        className="h-4 w-4 accent-[var(--color-primary)]"
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={() => setAssignOpen(false)}>Cancel</Button>
              <Button onClick={saveAssignments} isLoading={saving}>Save Assignments</Button>
            </div>
          </div>
        </div>
      )}

      {/* Module Edit Modal (View/Edit) */}
      {editModalOpen && editModule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setEditModalOpen(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              Edit Module
            </h3>
            <div className="mt-4 flex flex-col gap-4">
              <Input label="Name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
              <Input label="Code" value={editForm.code} onChange={(e) => setEditForm({ ...editForm, code: e.target.value })} readOnly />
              <Input label="Display Name" value={editForm.display_name} onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })} />
              <Input label="Description" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Status</span>
                <select
                  value={editForm.is_active ? 'active' : 'inactive'}
                  onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'active' })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" size="sm" onClick={() => setEditModalOpen(false)}>Cancel</Button>
              <Button size="sm" onClick={async () => {
                setSaving(true)
                try {
                  await superadminApi.updateModule(editModule.id, editForm)
                  addToast('Module updated successfully')
                  setEditModalOpen(false)
                  load()
                } catch (err) {
                  addToast(err.payload?.message || err.message || 'Failed to update module', 'error')
                } finally {
                  setSaving(false)
                }
              }} isLoading={saving}>
                Save
              </Button>
            </div>
          </div>
        </div>
      )}

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
