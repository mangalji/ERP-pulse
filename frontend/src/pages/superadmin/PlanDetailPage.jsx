import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import { superadminApi } from '../../services/superadmin.js'

export default function PlanDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadPlan = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await superadminApi.getPlan(id)
      setPlan(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load plan')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadPlan()
  }, [loadPlan])

  if (loading) {
    return (
      <AdminLayout title="Plan" breadcrumb="Plan">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </AdminLayout>
    )
  }

  if (error) {
    return (
      <AdminLayout title="Plan" breadcrumb="Plan">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error}</p>
        </Card>
      </AdminLayout>
    )
  }

  if (!plan) return null

  const enabledModules = plan.enabled_modules || []

  return (
    <AdminLayout title={plan.name} breadcrumb="Plan Detail">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin/plans')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Plans</span>
        </div>

        <PageHeader
          title={plan.name}
          subtitle={plan.description}
          actions={
            <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/plans`)}>
              Back to Plans
            </Button>
          }
        />

        <InfoCard
          title="Basic Information"
          items={[
            { label: 'Plan Name', value: plan.name },
            { label: 'Description', value: plan.description || '—' },
            { label: 'Status', value: <StatusBadge status={plan.status} /> },
            { label: 'Created Date', value: plan.created_at ? new Date(plan.created_at).toLocaleDateString() : '—' },
            { label: 'Updated Date', value: plan.updated_at ? new Date(plan.updated_at).toLocaleDateString() : '—' },
          ]}
        />

        <InfoCard
          title="Pricing"
          items={[
            { label: 'Monthly Price', value: `$${Number(plan.monthly_price || 0).toFixed(2)}` },
            { label: 'Yearly Price', value: `$${Number(plan.yearly_price || 0).toFixed(2)}` },
          ]}
        />

        <InfoCard
          title="Limits"
          items={[
            { label: 'Max Employees', value: plan.max_employees ?? 0 },
            { label: 'Max OCR Documents', value: plan.max_ocr_documents ?? 0 },
            { label: 'Max Storage (GB)', value: plan.max_storage_gb ?? 0 },
          ]}
        />

        <SectionCard
          title="Included Modules"
          subtitle={`${enabledModules.length} module${enabledModules.length !== 1 ? 's' : ''} included`}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {enabledModules.map((mod) => (
              <div
                key={mod.id}
                className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--color-ink)]">{mod.display_name || mod.name}</p>
                  <p className="text-xs text-[var(--color-muted)]">{mod.code}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        {plan.companies_using && plan.companies_using.length > 0 && (
          <SectionCard title="Companies Using This Plan">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                    <th className="pb-2 pr-4 font-medium">Company</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Start Date</th>
                    <th className="pb-2 font-medium">Expiry Date</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.companies_using.map((cp) => (
                    <tr key={cp.company_id} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-3 pr-4">
                        <button
                          onClick={() => navigate(`/admin/companies/${cp.company_id}`)}
                          className="font-medium text-[var(--color-primary)] hover:underline"
                        >
                          {cp.company_name}
                        </button>
                      </td>
                      <td className="py-3 pr-4"><StatusBadge status={cp.status} /></td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                        {cp.start_date ? new Date(cp.start_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3 text-[var(--color-ink-soft)]">
                        {cp.end_date ? new Date(cp.end_date).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )}
      </div>
    </AdminLayout>
  )
}
