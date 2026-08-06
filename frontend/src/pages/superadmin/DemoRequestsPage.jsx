import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { demoApi } from '../../services/demo.js'

const PAGE_SIZE = 10

export default function DemoRequestsPage() {
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await demoApi.list({ limit: PAGE_SIZE, offset })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load demo requests')
    } finally {
      setLoading(false)
    }
  }, [offset])

  useEffect(() => {
    load()
  }, [load])

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <AdminLayout title="Demo Requests" breadcrumb="Demo Requests">
      <div className="flex flex-col gap-6">
        <PageHeader title="Demo Requests" subtitle="Manage incoming demo requests." />

        <Card className="p-5">
          {loading ? (
            <p className="text-sm text-[var(--color-muted)]">Loading...</p>
          ) : error ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-sm text-[var(--color-negative)]">{error}</p>
              <Button intent="secondary" onClick={load}>Try again</Button>
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm text-[var(--color-muted)]">No demo requests found.</p>
          ) : (
            <>
              <div className="flex flex-col gap-3">
                {rows.map((row) => (
                  <div
                    key={row.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] p-4"
                  >
                    <div>
                      <p className="text-sm font-medium text-[var(--color-ink)]">{row.company_name}</p>
                      <p className="text-xs text-[var(--color-muted)]">{row.business_email} · {row.demo_request_number}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                        row.status === 'NEW' ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' :
                        row.status === 'APPROVED' ? 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]' :
                        'bg-[var(--color-canvas)] text-[var(--color-muted)]'
                      }`}>{row.status}</span>
                      <Button intent="secondary" size="sm" onClick={() => navigate(`/admin/demo-requests/${row.id}`)}>
                        View
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

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
            </>
          )}
        </Card>

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </AdminLayout>
  )
}
