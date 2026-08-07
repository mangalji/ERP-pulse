import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'

export default function CompanyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(null)

  const loadCompany = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await superadminApi.getCompany(id)
      setCompany(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load company')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCompany()
  }, [id])

  const runAction = async (action, _label) => {
    setConfirm(null)
    try {
      await action()
      addToast(`Action completed successfully`)
      loadCompany()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    }
  }

  if (loading) {
    return (
      <AdminLayout title="Company" breadcrumb="Company">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </AdminLayout>
    )
  }

  if (error) {
    return (
      <AdminLayout title="Company" breadcrumb="Company">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error}</p>
          <Button intent="secondary" onClick={loadCompany} className="mt-4">Try again</Button>
        </Card>
      </AdminLayout>
    )
  }

  if (!company) return null

  const plan = company.current_plan
  const nsConnected = company.netsuite_connected

  return (
    <AdminLayout title={company.name} breadcrumb="Company Detail">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin/companies')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Companies</span>
        </div>
        <PageHeader
          title={company.name}
          subtitle={company.code}
          actions={
            <div className="flex gap-2">
              <Button size="sm" onClick={() => navigate(`/admin/companies/${company.id}/subscription`)}>
                View Subscription
              </Button>
              <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/employees?company_id=${company.id}`)}>
                View Employees
              </Button>
            </div>
          }
        />

        <InfoCard
          title="Basic Information"
          items={[
            { label: 'Company Name', value: company.name },
            { label: 'Company Code', value: company.code },
            { label: 'Status', value: <StatusBadge status={company.status} /> },
            { label: 'Created Date', value: company.created_at ? new Date(company.created_at).toLocaleDateString() : '—' },
            { label: 'Updated Date', value: company.updated_at ? new Date(company.updated_at).toLocaleDateString() : '—' },
          ]}
        />

        <InfoCard
          title="Contact Information"
          items={[
            { label: 'Contact Email', value: company.contact_email || '—' },
            { label: 'Contact Phone', value: company.contact_phone || '—' },
            { label: 'Country', value: company.country || '—' },
          ]}
        />

        <InfoCard
          title="Subscription"
          items={[
            { label: 'Assigned Plan', value: plan ? plan.plan_name : 'No Active Plan' },
            { label: 'Plan Type', value: plan ? plan.status : '—' },
            { label: 'Start Date', value: plan && plan.start_date ? new Date(plan.start_date).toLocaleDateString() : '—' },
            { label: 'Expiry Date', value: plan && plan.end_date ? new Date(plan.end_date).toLocaleDateString() : '—' },
            { label: 'Auto-Renew', value: plan ? (plan.is_auto_renew ? 'Yes' : 'No') : '—' },
          ]}
        />

        {plan && (
          <InfoCard
            title="Subscription Status"
            items={[
              { label: 'Plan', value: plan.plan_name || '—' },
              { label: 'Modules Enabled', value: company.assigned_modules?.length ?? 0 },
              {
                label: 'Employees Used',
                value: `${company.user_count ?? 0}${plan.max_employees ? ` / ${plan.max_employees}` : ''}`,
              },
              { label: 'Storage Used', value: company.storage_used || '0 GB' },
              {
                label: 'Plan Expiry',
                value: plan.end_date ? (() => {
                  const daysLeft = Math.ceil((new Date(plan.end_date) - new Date()) / (1000 * 60 * 60 * 24))
                  return `${daysLeft > 0 ? `${daysLeft} days` : 'Expired'} (${new Date(plan.end_date).toLocaleDateString()})`
                })() : '—',
              },
            ]}
          />
        )}

        <InfoCard
          title="NetSuite"
          items={[
            { label: 'Connected', value: nsConnected ? <StatusBadge status="true" /> : <StatusBadge status="false" /> },
            { label: 'Account ID', value: company.netsuite_account_id || '—' },
            { label: 'Environment', value: company.netsuite_environment || '—' },
            { label: 'Last Sync', value: company.netsuite_last_sync ? new Date(company.netsuite_last_sync).toLocaleString() : '—' },
          ]}
        />

        <InfoCard
          title="Employees"
          items={[
            { label: 'Total Employees', value: company.user_count ?? 0 },
            { label: 'Active Employees', value: company.active_user_count ?? 0 },
          ]}
        />

        {company.assigned_modules && company.assigned_modules.length > 0 && (
          <SectionCard title="Assigned Modules">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {company.assigned_modules.map((mod) => (
                <div key={mod.id} className="rounded-lg border border-[var(--color-border)] p-3">
                  <p className="text-sm font-medium text-[var(--color-ink)]">{mod.display_name || mod.name}</p>
                  <p className="text-xs text-[var(--color-muted)]">{mod.code}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        <SectionCard
          title="Actions"
          actions={
            <div className="flex gap-2">
              <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/companies/${company.id}/subscription`)}>
                Assign Plan
              </Button>
              <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/companies/${company.id}/subscription?tab=modules`)}>
                Assign Modules
              </Button>
              <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/employees?company_id=${company.id}`)}>
                View Employees
              </Button>
              {company.status === 'SUSPENDED' ? (
                <Button size="sm" onClick={() => setConfirm({ action: () => superadminApi.activateCompany(company.id), label: 'Activate' })}>
                  Activate
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => setConfirm({ action: () => superadminApi.suspendCompany(company.id), label: 'Suspend' })}
                >
                  Suspend
                </Button>
              )}
            </div>
          }
        />

        <Toast toasts={toasts} removeToast={removeToast} />

        <ConfirmDialog
          open={!!confirm}
          title={confirm ? `${confirm.label} company?` : ''}
          message={confirm ? `Are you sure you want to ${confirm.label.toLowerCase()} ${company.name}?` : ''}
          confirmLabel={confirm?.label}
          intent="primary"
          onConfirm={() => confirm && runAction(confirm.action, confirm.label)}
          onCancel={() => setConfirm(null)}
        />
      </div>
    </AdminLayout>
  )
}
