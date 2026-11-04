import { useCallback, useEffect, useState } from 'react'
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
import { formatDate, formatDateTime } from '../../utils/formatDate.js'

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
  const [subscriptionModalOpen, setSubscriptionModalOpen] = useState(false)
  const [connectionsOpen, setConnectionsOpen] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editError, setEditError] = useState('')

  const [editForm, setEditForm] = useState({
    name: '',
    contact_email: '',
    contact_phone_country_code: '',
    contact_phone: '',
    country: '',
  })

  const loadCompany = useCallback(async () => {
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
  }, [id])

  useEffect(() => {
    void loadCompany()
  }, [loadCompany])

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
    const storedPhoneDigits = (company.contact_phone || '').replace(/\D/g, '')
    const dialCodeDigits = (company.contact_phone_country_code || '').replace(/\D/g, '')

    setEditForm({
      name: company.name || '',
      contact_email: company.contact_email || '',
      contact_phone_country_code:
        company.contact_phone_country_code || '',
      contact_phone:
        dialCodeDigits && storedPhoneDigits.startsWith(dialCodeDigits)
          ? storedPhoneDigits.slice(dialCodeDigits.length)
          : storedPhoneDigits,
      country: company.country || '',
    })

    setEditError('')
    setEditOpen(true)
  }

  const handleEditSave = async (event) => {
    event.preventDefault()

    setEditError('')

    const name = editForm.name.trim()
    const phone = editForm.contact_phone.replace(/\D/g, '')
    const country = editForm.country.trim()

    if (!name) {
      setEditError('Company name is required.')
      return
    }

    setSaving(true)

    try {
      await superadminApi.updateCompany(company.id, {
        name,
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
  const completedTransaction = company.transactions?.find(
  (tx) => tx.payment_status === 'SUCCESS',
)
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
                onClick={() => setSubscriptionModalOpen(true)}
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
                  ? formatDateTime(company.created_at)
                  : '—'}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                Last Updated
              </p>

              <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                {company.updated_at
                  ? formatDateTime(company.updated_at)
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
                  ? ` Deleted on ${formatDateTime(company.deleted_at)}.`
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
                    {plan.name || '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Plan Status
                  </p>

                  <p className="mt-1 font-semibold text-[var(--color-ink)]">
                    {plan.subscription_status || '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Start Date
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.start_date
                      ? formatDate(plan.start_date)
                      : '—'}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-[var(--color-muted)]">
                    Expiry Date
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {plan.end_date
                      ? formatDate(plan.end_date)
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
    </p>
  </div>

  <div>
    <p className="text-xs text-[var(--color-muted)]">
      Original Price
    </p>

    <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
      ₹
      {Number(
        completedTransaction?.original_amount ?? plan.price ?? 0,
      ).toFixed(2)}
    </p>
  </div>

  <div>
    <p className="text-xs text-[var(--color-muted)]">
      Discount
    </p>

    <p className="mt-1 text-sm font-medium text-[var(--color-ink-soft)]">
      {completedTransaction
        ? `₹${Number(
            completedTransaction.discount_amount || 0,
          ).toFixed(2)}`
        : 'None'}
    </p>
  </div>

  <div>
    <p className="text-xs text-[var(--color-muted)]">
      Final Price
    </p>

    <p className="mt-1 font-semibold text-[var(--color-primary)]">
      ₹
      {Number(
        completedTransaction?.total_amount ?? plan.price ?? 0,
      ).toFixed(2)}
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
            <SectionCard
              title="NetSuite"
              actions={
                <Button
                  size="sm"
                  intent="secondary"
                  onClick={() => setConnectionsOpen(true)}
                >
                  Check all connections ({company.netsuite_connection_count || 0})
                </Button>
              }
            >
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg border border-[var(--color-border)] p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    Connection Status
                  </p>
            
                  <div className="mt-2">
                    {nsConnected ? (
                      <StatusBadge status="true" />
                    ) : (
                      <StatusBadge status="false" />
                    )}
                  </div>
                </div>
                  
                <div className="rounded-lg border border-[var(--color-border)] p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    Account ID
                  </p>
                  
                  <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                    {company.netsuite_account_id || '—'}
                  </p>
                </div>
                  
                <div className="rounded-lg border border-[var(--color-border)] p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    Environment
                  </p>
                  
                  <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                    {company.netsuite_environment || '—'}
                  </p>
                </div>
                  
                <div className="rounded-lg border border-[var(--color-border)] p-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    Last Sync
                  </p>
                  
                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                    {company.netsuite_last_sync
                      ? formatDateTime(company.netsuite_last_sync)
                      : '—'}
                  </p>
                </div>
              </div>
            </SectionCard>


        {connectionsOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40" onClick={() => setConnectionsOpen(false)} />
            <Card className="relative max-h-[80vh] w-full max-w-3xl overflow-y-auto p-6">
              <div className="mb-5 flex items-start justify-between">
                <div>
                  <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">NetSuite connections</h2>
                  <p className="mt-1 text-sm text-[var(--color-muted)]">{company.netsuite_connection_count || 0} connection{company.netsuite_connection_count === 1 ? '' : 's'} for {company.name}. Read-only for Super Admin.</p>
                </div>
                <button type="button" onClick={() => setConnectionsOpen(false)} className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]" aria-label="Close">✕</button>
              </div>
              {(company.netsuite_connections || []).length === 0 ? (
                <p className="text-sm text-[var(--color-muted)]">No NetSuite connections for this company.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {company.netsuite_connections.map((connection) => (
                    <div key={connection.id} className="rounded-lg border border-[var(--color-border)] p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-[var(--color-ink)]">{connection.client_name || 'Unnamed connection'}</p>
                          <p className="mt-1 text-sm text-[var(--color-muted)]">{connection.netsuite_account_id} · {connection.environment || '—'}</p>
                        </div>
                        <div className="flex gap-2"><StatusBadge status={connection.status} />{connection.is_current && <span className="rounded-full bg-[var(--color-positive-soft)] px-2 py-1 text-xs font-medium text-[var(--color-positive)]">Current connection</span>}</div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--color-muted)]">Last sync: {connection.last_synced_at ? formatDateTime(connection.last_synced_at) : '—'}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}

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
                            {country.label}
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
                      readOnly
                      disabled
                      maxLength={40}
                      className="cursor-not-allowed rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3.5 py-2.5 text-sm text-[var(--color-ink-soft)] outline-none"
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
                      readOnly
                      disabled
                      className="cursor-not-allowed rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3.5 py-2.5 text-sm text-[var(--color-ink-soft)] outline-none"
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
                            e.target.value.replace(/\D/g, ''),
                        }))
                      }
                      maxLength={15}
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
        {subscriptionModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="absolute inset-0 bg-black/40"
              onClick={() => setSubscriptionModalOpen(false)}
            />
            <div className="relative max-h-[calc(100vh-80px)] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <div className="mb-5 flex items-center justify-between">
                <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                  Subscription — {company.name}
                </h2>
                <button
                  onClick={() => setSubscriptionModalOpen(false)}
                  className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {(() => {
                const pendingTx = transactions.find(tx => tx.payment_status === 'PENDING')
                const completedTx = transactions.find(tx => tx.payment_status === 'SUCCESS')
                const activePlan = company.current_plan

                if (!activePlan && !pendingTx) {
                  return (
                    <div className="rounded-lg border border-dashed border-[var(--color-border)] p-6 text-center">
                      <p className="text-sm font-medium text-[var(--color-ink)]">No subscription assigned</p>
                    </div>
                  )
                }

                return (
                  <div className="flex flex-col gap-4">
                    {activePlan && (
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Plan Name</p>
                          <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{activePlan.name || '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Subscription Status</p>
                          <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{activePlan.subscription_status || '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Original Price</p>
                          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">₹{Number(completedTx?.original_amount ?? activePlan.price ?? 0,).toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Discount</p>
                          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{completedTx
  ? `₹${Number(
      completedTx.discount_amount || 0,
    ).toFixed(2)}`
  : '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Final Price</p>
                          <p className="mt-1 text-sm font-semibold text-[var(--color-primary)]">₹{Number(
  completedTx?.total_amount ?? activePlan.price ?? 0,
).toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Validity</p>
                          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{activePlan.validity_days ?? 30} days</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Start Date</p>
                          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{activePlan.start_date ? formatDate(activePlan.start_date) : '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">End Date</p>
                          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{activePlan.end_date ? formatDate(activePlan.end_date) : '—'}</p>
                        </div>
                      </div>
                    )}

                    {completedTx && (
                      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
                        <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)] mb-2">Transaction Details</p>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          <div>
                            <p className="text-xs text-[var(--color-muted)]">Transaction ID</p>
                            <p className="text-sm font-mono text-[var(--color-ink)]">{completedTx.transaction_id || '—'}</p>
                          </div>
                          <div>
                            <p className="text-xs text-[var(--color-muted)]">Payment Status</p>
                            <p className="text-sm text-[var(--color-ink-soft)]">Completed</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {pendingTx && (
                      <div className="flex flex-col gap-4">
                        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)] mb-2">Pending Transaction</p>
                          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            <div>
                              <p className="text-xs text-[var(--color-muted)]">Transaction ID</p>
                              <p className="text-sm font-mono text-[var(--color-ink)]">{pendingTx.transaction_id || '—'}</p>
                            </div>
                            <div>
                              <p className="text-xs text-[var(--color-muted)]">Payment Status</p>
                              <p className="text-sm text-[var(--color-ink-soft)]">Pending</p>
                            </div>
                          </div>
                        </div>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Plan Name</p>
                            <p className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{pendingTx.plan__name || '—'}</p>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Original Price</p>
                            <p className="mt-1 text-sm text-[var(--color-ink-soft)]">₹{Number(pendingTx.original_amount || 0).toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Discount</p>
                            <p className="mt-1 text-sm text-[var(--color-ink-soft)]">-₹{Number(pendingTx.discount_amount || 0).toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">Final Price</p>
                            <p className="mt-1 text-sm font-semibold text-[var(--color-primary)]">₹{Number(pendingTx.total_amount || 0).toFixed(2)}</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })()}
            </div>
          </div>
        )}

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
