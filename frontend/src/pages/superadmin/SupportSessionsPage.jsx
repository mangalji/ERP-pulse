import { useState, useEffect, useCallback } from 'react'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

const PAGE_SIZE = 10

export default function SupportSessionsPage() {
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [companies, setCompanies] = useState([])
  const [employees, setEmployees] = useState([])
  const [startOpen, setStartOpen] = useState(false)
  const [form, setForm] = useState({ company_id: '', support_user_id: '', reason: '' })
  const [saving, setSaving] = useState(false)
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listSupportSessions({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load support sessions')
    } finally {
      setLoading(false)
    }
  }, [search, offset])

  useEffect(() => {
    load()
  }, [load])

  const openStart = async () => {
    setForm({ company_id: '', support_user_id: '', reason: '' })
    setStartOpen(true)
    try {
      const [compData, empData] = await Promise.all([
        superadminApi.listCompanies({ limit: 100 }),
        superadminApi.listEmployees({ limit: 100 }),
      ])
      setCompanies(compData.results || [])
      setEmployees(empData.results || [])
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load options', 'error')
    }
  }

  const handleStart = async () => {
    setSaving(true)
    try {
      await superadminApi.startSupportSession(form)
      addToast('Support session started')
      setStartOpen(false)
      setOffset(0)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to start session', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleEnd = async (session) => {
    setSaving(true)
    try {
      await superadminApi.endSupportSession(session.id)
      addToast('Support session ended')
      setConfirm(null)
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to end session', 'error')
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    {
      key: 'reason',
      header: 'Reason',
      render: (row) => <span className="font-medium text-[var(--color-ink)]">{row.reason}</span>,
    },
    {
      key: 'company_name',
      header: 'Company',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.company_name || '—'}</span>,
    },
    {
      key: 'support_user_email',
      header: 'Support User',
      render: (row) => (
        <div>
          <p className="text-[var(--color-ink)]">{row.support_user_name || '—'}</p>
          <p className="text-xs text-[var(--color-muted)]">{row.support_user_email || ''}</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: 'started_at',
      header: 'Started',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.started_at ? new Date(row.started_at).toLocaleString() : '—'}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        row.status === 'ACTIVE' ? (
          <button
            onClick={() => setConfirm({ session: row })}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
          >
            End Session
          </button>
        ) : (
          <span className="text-xs text-[var(--color-muted)]">—</span>
        )
      ),
    },
  ]

  return (
    <AdminLayout title="Support Sessions" breadcrumb="Support Sessions">
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Support Sessions"
          subtitle="Track support sessions with client companies."
          actions={<Button onClick={openStart}>Start Session</Button>}
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setOffset(0) }} placeholder="Search sessions..." />
            <span className="text-xs text-[var(--color-muted)]">{count} session{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No support sessions"
            emptyDescription="Start a support session to assist a company."
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

      {/* Start Session Modal */}
      {startOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setStartOpen(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Start Support Session</h3>
            <div className="mt-4 flex flex-col gap-4">
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Company</span>
                <select
                  value={form.company_id}
                  onChange={(e) => setForm({ ...form, company_id: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select a company...</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Support User</span>
                <select
                  value={form.support_user_id}
                  onChange={(e) => setForm({ ...form, support_user_id: e.target.value })}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select a support user...</option>
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>{e.email}</option>
                  ))}
                </select>
              </label>
              <Input label="Reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={() => setStartOpen(false)}>Cancel</Button>
              <Button onClick={handleStart} isLoading={saving}>Start</Button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirm}
        title="End support session?"
        message={confirm ? `Are you sure you want to end this session for ${confirm.session.company_name}?` : ''}
        confirmLabel="End Session"
        onConfirm={() => confirm && handleEnd(confirm.session)}
        onCancel={() => setConfirm(null)}
        loading={saving}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}
