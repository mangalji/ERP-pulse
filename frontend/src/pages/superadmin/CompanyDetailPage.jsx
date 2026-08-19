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

const COUNTRY_OPTIONS = [
  { value: 'IN', label: 'India', dialCode: '+91' },
  { value: 'US', label: 'United States', dialCode: '+1' },
  { value: 'GB', label: 'United Kingdom', dialCode: '+44' },
  { value: 'AU', label: 'Australia', dialCode: '+61' },
  { value: 'CA', label: 'Canada', dialCode: '+1' },
  { value: 'AE', label: 'United Arab Emirates', dialCode: '+971' },
  { value: 'SG', label: 'Singapore', dialCode: '+65' },
  { value: 'DE', label: 'Germany', dialCode: '+49' },
  { value: 'FR', label: 'France', dialCode: '+33' },
  { value: 'JP', label: 'Japan', dialCode: '+81' },
]

export default function CompanyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(null)

  const [editOpen, setEditOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editError, setEditError] = useState('')

  const [editForm, setEditForm] = useState({
    name: '',
    code: '',
    contact_email: '',
    contact_phone_country_code: '',
    contact_phone: '',
    country: '',
  })

  const loadCompany = async () => {
    setLoading(true)
    setError('')

    try {
      const data = await superadminApi.getCompany(id)
      setCompany(data)
    } catch (err) {
      setError(
        err.payload?.message ||
          err.payload?.detail ||
          err.message ||
          'Failed to load company',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCompany()
  }, [id])

  const runAction = async (action) => {
    setConfirm(null)

    try {
      await action()
      addToast('Action completed successfully')
      await loadCompany()
    } catch (err) {
      addToast(
        err.payload?.message ||
          err.payload?.detail ||
          err.message ||
          'Action failed',
        'error',
      )
    }
  }

  const openEdit = () => {
    setEditForm({
      name: company.name || '',
      code: company.code || '',
      contact_email: company.contact_email || '',
      contact_phone_country_code:
        company.contact_phone_country_code || '',
      contact_phone: company.contact_phone || '',
      country: company.country || '',
    })

    setEditError('')
    setEditOpen(true)
  }

  const handleEditSave = async (event) => {
    event.preventDefault()

    setEditError('')

    const name = editForm.name.trim()
    const code = editForm.code.trim()
    const contactEmail = editForm.contact_email.trim()
    const phone = editForm.contact_phone.trim()
    const country = editForm.country.trim()

    if (!name) {
      setEditError('Company name is required.')
      return
    }

    if (!code) {
      setEditError('Company code is required.')
      return
    }

    if (
      contactEmail &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contactEmail)
    ) {
      setEditError('Please enter a valid contact email.')
      return
    }

    setSaving(true)

    try {
      await superadminApi.updateCompany(company.id, {
        name,
        code,
        contact_email: contactEmail,
        contact_phone_country_code:
          editForm.contact_phone_country_code.trim(),
        contact_phone: phone,
        country,
      })

      addToast('Company updated successfully')
      setEditOpen(false)

      await loadCompany()
    } catch (err) {
      setEditError(
        err.payload?.detail ||
          err.payload?.message ||
          err.message ||
          'Failed to update company',
      )
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <AdminLayout
        title="Company"
        breadcrumb="Company"
      >
        <Card className="p-6">
          <p className="text-sm text-[var(--color-muted)]">
            Loading...
          </p>
        </Card>
      </AdminLayout>
    )
  }

  if (error) {
    return (
      <AdminLayout
        title="Company"
        breadcrumb="Company"
      >
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">
            {error}
          </p>

          <Button
            intent="secondary"
            onClick={loadCompany}
            className="mt-4"
          >
            Try again
          </Button>
        </Card>
      </AdminLayout>
    )
  }

  if (!company) {
    return null
  }

  const plan = company.current_plan
  const nsConnected = company.netsuite_connected
  const isSuspended = company.status === 'SUSPENDED'

  const actionLabel = isSuspended
    ? 'Activate'
    : 'Suspend'

  const actionHandler = isSuspended
    ? () => superadminApi.activateCompany(company.id)
    : () => superadminApi.suspendCompany(company.id)

  const suspensionReasonLabel = (() => {
    switch (company.suspension_reason) {
      case 'MANUAL':
        return 'Manual Suspension'

      case 'PLAN':
        return 'Subscription / Plan'

      case 'DELETED':
        return 'Soft Deleted'

      case 'NONE':
        return 'None'

      default:
        return company.suspension_reason || '—'
    }
  })()

  return (
    <AdminLayout
      title={company.name}
      breadcrumb="Company Detail"
    >
      <div className="flex flex-col gap-6">

        {/* Back navigation */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() =>
              navigate('/admin/companies')
            }
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-4 w-4"
            >
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>

          <span className="text-sm text-[var(--color-muted)]">
            Companies
          </span>
        </div>

        {/* Header */}
        <PageHeader
          title={company.name}
          subtitle={company.code}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={company.status} />

              <Button
                size="sm"
                intent="secondary"
                onClick={openEdit}
              >
                Edit Company
              </Button>

              <Button
                size="sm"
                intent="secondary"
                onClick={() =>
                  navigate(
                    `/admin/employees?company_id=${company.id}`,
                  )
                }
              >
                View Employees
              </Button>

              <Button
                size="sm"
                onClick={() =>
                  navigate(
                    `/admin/companies/${company.id}/subscription`,
                  )
                }
              >
                View Subscription
              </Button>

              <Button
                size="sm"
                intent="secondary"
                onClick={() =>
                  setConfirm({
                    action: actionHandler,
                    label: actionLabel,
                  })
                }
              >
                {actionLabel}
              </Button>
            </div>
          }
        />

        {/* Company Overview */}
        <SectionCard title="Company Overview">
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Company Name
              </p>

              <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                {company.name}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Company Code
              </p>

              <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                {company.code}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Status
              </p>

              <div className="mt-2">
                <StatusBadge status={company.status} />
              </div>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Suspension Reason
              </p>

              <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
                {suspensionReasonLabel}
              </p>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 border-t border-[var(--color-border)] pt-5 md:grid-cols-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Created
              </p>

              <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                {company.created_at
                  ? new Date(
                      company.created_at,
                    ).toLocaleString()
                  : '—'}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Last Updated
              </p>

              <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                {company.updated_at
                  ? new Date(
                      company.updated_at,
                    ).toLocaleString()
                  : '—'}
              </p>
            </div>
          </div>

          {company.is_deleted && (
            <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
              <p className="text-sm font-semibold text-red-700">
                This company is soft deleted.
              </p>

              <p className="mt-1 text-xs text-red-600">
                Company operations are disabled during
                the recovery period.
                {company.deleted_at
                  ? ` Deleted on ${new Date(
                      company.deleted_at,
                    ).toLocaleString()}.`
                  : ''}
              </p>
            </div>
          )}
        </SectionCard>

        {/* Contact + Employees */}
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">

          <InfoCard
            title="Contact Information"
            items={[
              {
                label: 'Contact Email',
                value:
                  company.contact_email || '—',
              },
              {
                label: 'Admin User Email',
                value:
                  company.admin_email || '—',
              },
              {
                label: 'Contact Phone',
                value:
                  company.contact_phone || '—',
              },
              {
                label: 'Country',
                value:
                  company.country || '—',
              },
            ]}
          />

          <SectionCard
            title="Employee Overview"
            actions={
              <Button
                size="sm"
                intent="secondary"
                onClick={() =>
                  navigate(
                    `/admin/employees?company_id=${company.id}`,
                  )
                }
              >
                View Employees
              </Button>
            }
          >
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-muted)]">
                  Total Employees
                </p>

                <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">
                  {company.user_count ?? 0}
                </p>
              </div>

              <div className="rounded-lg border border-[var(--color-border)] p-4">
                <p className="text-xs text-[var(--color-muted)]">
                  Active Employees
                </p>

                <p className="mt-1 text-2xl font-semibold text-[var(--color-ink)]">
                  {company.active_user_count ?? 0}
                </p>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Subscription */}
        <SectionCard
          title="Subscription"
          actions={
            <Button
              size="sm"
              onClick={() =>
                navigate(
                  `/admin/companies/${company.id}/subscription`,
                )
              }
            >
              Manage Subscription
            </Button>
          }
        >
          {plan ? (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Plan
                  </p>

                  <p className="mt-1 font-semibold text-[var(--color-ink)]">
                    {plan.plan_name || '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Plan Status
                  </p>

                  <p className="mt-1 font-semibold text-[var(--color-ink)]">
                    {plan.status || '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Start Date
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.start_date
                      ? new Date(
                          plan.start_date,
                        ).toLocaleDateString()
                      : '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Expiry Date
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.end_date
                      ? new Date(
                          plan.end_date,
                        ).toLocaleDateString()
                      : '—'}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-2 gap-4 border-t border-[var(--color-border)] pt-5 lg:grid-cols-4">

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Employees
                  </p>

                  <p className="mt-1 font-semibold text-[var(--color-ink)]">
                    {company.user_count ?? 0}
                    {plan.max_employees
                      ? ` / ${plan.max_employees}`
                      : ''}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Billing Cycle
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.billing_cycle ||
                      'MONTHLY'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Auto Renew
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.is_auto_renew
                      ? 'Yes'
                      : 'No'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Final Price
                  </p>

                  <p className="mt-1 font-semibold text-[var(--color-primary)]">
                    ₹
                    {Number(
                      plan.final_price || 0,
                    ).toFixed(2)}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-1 gap-4 border-t border-[var(--color-border)] pt-5 md:grid-cols-3">

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Original Price
                  </p>

                  <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
                    ₹
                    {Number(
                      plan.original_price || 0,
                    ).toFixed(2)}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Discount
                  </p>

                  <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
                    {plan.discount_display ||
                      'None'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Subscription Employees Limit
                  </p>

                  <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
                    {plan.max_employees ??
                      'Unlimited / Not specified'}
                  </p>
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-6 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                No active subscription
              </p>

              <p className="mt-1 text-xs text-[var(--color-muted)]">
                Assign a plan to activate
                subscription-based services.
              </p>

              <Button
                size="sm"
                className="mt-4"
                onClick={() =>
                  navigate(
                    `/admin/companies/${company.id}/subscription`,
                  )
                }
              >
                Assign Plan
              </Button>
            </div>
          )}
        </SectionCard>

        {/* Transactions */}
        {company.transactions &&
          company.transactions.length > 0 && (
            <SectionCard title="Transactions">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                      <th className="pb-2 pr-4 font-medium">
                        Transaction ID
                      </th>

                      <th className="pb-2 pr-4 font-medium">
                        Plan
                      </th>

                      <th className="pb-2 pr-4 font-medium">
                        Amount
                      </th>

                      <th className="pb-2 pr-4 font-medium">
                        Discount
                      </th>

                      <th className="pb-2 pr-4 font-medium">
                        Final Amount
                      </th>

                      <th className="pb-2 pr-4 font-medium">
                        Status
                      </th>

                      <th className="pb-2 font-medium">
                        Date
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {company.transactions.map(
                      (tx) => (
                        <tr
                          key={tx.transaction_id}
                          className="border-b border-[var(--color-border)] last:border-0"
                        >
                          <td className="py-3 pr-4 font-mono text-xs text-[var(--color-ink)]">
                            {tx.transaction_id}
                          </td>

                          <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                            {tx.plan_name || '—'}
                          </td>

                          <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                            ₹
                            {Number(
                              tx.original_amount ||
                                0,
                            ).toFixed(2)}
                          </td>

                          <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                            -₹
                            {Number(
                              (tx.original_amount ||
                                0) -
                                (tx.final_amount ||
                                  0),
                            ).toFixed(2)}
                          </td>

                          <td className="py-3 pr-4 font-medium text-[var(--color-primary)]">
                            ₹
                            {Number(
                              tx.final_amount ||
                                0,
                            ).toFixed(2)}
                          </td>

                          <td className="py-3 pr-4 capitalize">
                            {tx.payment_status ||
                              '—'}
                          </td>

                          <td className="py-3 pr-4 text-[var(--color-muted)]">
                            {tx.created_at
                              ? new Date(
                                  tx.created_at,
                                ).toLocaleDateString()
                              : '—'}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}

        {/* NetSuite */}
        <InfoCard
          title="NetSuite"
          items={[
            {
              label: 'Connected',
              value: nsConnected ? (
                <StatusBadge status="true" />
              ) : (
                <StatusBadge status="false" />
              ),
            },
            {
              label: 'Account ID',
              value:
                company.netsuite_account_id ||
                '—',
            },
            {
              label: 'Environment',
              value:
                company.netsuite_environment ||
                '—',
            },
            {
              label: 'Last Sync',
              value:
                company.netsuite_last_sync
                  ? new Date(
                      company.netsuite_last_sync,
                    ).toLocaleString()
                  : '—',
            },
          ]}
        />

        {/* Assigned Modules */}
        <SectionCard
          title="Assigned Modules"
          actions={
            <Button
              size="sm"
              intent="secondary"
              onClick={() =>
                navigate(
                  `/admin/companies/${company.id}/subscription?tab=modules`,
                )
              }
            >
              Manage Modules
            </Button>
          }
        >
          {company.assigned_modules &&
          company.assigned_modules.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {company.assigned_modules.map(
                (mod) => (
                  <div
                    key={mod.id}
                    className="rounded-lg border border-[var(--color-border)] p-4"
                  >
                    <p className="text-sm font-medium text-[var(--color-ink)]">
                      {mod.display_name ||
                        mod.name}
                    </p>

                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                      {mod.code}
                    </p>
                  </div>
                ),
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-6 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                No modules assigned
              </p>

              <p className="mt-1 text-xs text-[var(--color-muted)]">
                Assign modules from the subscription
                management page.
              </p>

              <Button
                size="sm"
                intent="secondary"
                className="mt-4"
                onClick={() =>
                  navigate(
                    `/admin/companies/${company.id}/subscription?tab=modules`,
                  )
                }
              >
                Assign Modules
              </Button>
            </div>
          )}
        </SectionCard>

        {/* Edit Company Modal */}
        {editOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="absolute inset-0 bg-black/40"
              onClick={() => {
                if (!saving) {
                  setEditOpen(false)
                }
              }}
            />

            <div className="relative max-h-[calc(100vh-80px)] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">

              <div className="mb-5">
                <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                  Edit Company
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Update company identification and
                  contact information.
                </p>
              </div>

              {editError && (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {editError}
                </div>
              )}

              <form
                onSubmit={handleEditSave}
                className="grid grid-cols-1 gap-4 md:grid-cols-2"
              >

                {/* Company Name */}
                <div className="md:col-span-2">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Company Name
                    </span>

                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) =>
                        setEditForm((prev) => ({
                          ...prev,
                          name: e.target.value,
                        }))
                      }
                      required
                      maxLength={100}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    />
                  </label>
                </div>

                {/* Company Code */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Company Code
                    </span>

                    <input
                      type="text"
                      value={editForm.code}
                      onChange={(e) =>
                        setEditForm((prev) => ({
                          ...prev,
                          code: e.target.value,
                        }))
                      }
                      required
                      maxLength={20}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    />
                  </label>
                </div>

                {/* Country */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Country
                    </span>

                    <select
                      value={editForm.country}
                      onChange={(e) => {
                        const selected =
                          COUNTRY_OPTIONS.find(
                            (item) =>
                              item.value ===
                              e.target.value,
                          )

                        setEditForm((prev) => ({
                          ...prev,
                          country:
                            e.target.value,
                          contact_phone_country_code:
                            selected?.dialCode ||
                            prev.contact_phone_country_code,
                        }))
                      }}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    >
                      <option value="">
                        Select country
                      </option>

                      {COUNTRY_OPTIONS.map(
                        (country) => (
                          <option
                            key={country.value}
                            value={country.value}
                          >
                            {country.label} (
                            {country.dialCode})
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                </div>

                {/* Contact Email */}
                <div className="md:col-span-2">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Contact Email
                    </span>

                    <input
                      type="email"
                      value={editForm.contact_email}
                      onChange={(e) =>
                        setEditForm((prev) => ({
                          ...prev,
                          contact_email:
                            e.target.value,
                        }))
                      }
                      maxLength={100}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    />
                  </label>
                </div>

                {/* Phone Code */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Phone Code
                    </span>

                    <input
                      type="text"
                      value={
                        editForm.contact_phone_country_code
                      }
                      onChange={(e) =>
                        setEditForm((prev) => ({
                          ...prev,
                          contact_phone_country_code:
                            e.target.value,
                        }))
                      }
                      maxLength={6}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    />
                  </label>
                </div>

                {/* Contact Phone */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Contact Phone
                    </span>

                    <input
                      type="tel"
                      value={editForm.contact_phone}
                      onChange={(e) =>
                        setEditForm((prev) => ({
                          ...prev,
                          contact_phone:
                            e.target.value.replace(
                              /[^\d\s()+-]/g,
                              '',
                            ),
                        }))
                      }
                      maxLength={20}
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    />
                  </label>
                </div>

                {/* Modal Footer */}
                <div className="flex justify-end gap-2 border-t border-[var(--color-border)] pt-4 md:col-span-2">
                  <Button
                    type="button"
                    intent="secondary"
                    disabled={saving}
                    onClick={() =>
                      setEditOpen(false)
                    }
                  >
                    Cancel
                  </Button>

                  <Button
                    type="submit"
                    isLoading={saving}
                  >
                    Save Changes
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Toast */}
        <Toast
          toasts={toasts}
          removeToast={removeToast}
        />

        {/* Confirmation Dialog */}
        <ConfirmDialog
          open={!!confirm}
          title={
            confirm
              ? `${confirm.label} company?`
              : ''
          }
          message={
            confirm
              ? `Are you sure you want to ${confirm.label.toLowerCase()} ${company.name}?`
              : ''
          }
          confirmLabel={confirm?.label}
          intent="primary"
          onConfirm={() =>
            confirm &&
            runAction(confirm.action)
          }
          onCancel={() => setConfirm(null)}
        />
      </div>
    </AdminLayout>
  )
}