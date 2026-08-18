import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Card from '../../components/ui/Card.jsx'
// import InfoCard from '../../components/superadmin/InfoCard.jsx' // unused after drawer removal
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { superadminApi } from '../../services/superadmin.js'
import {
  COUNTRY_OPTIONS,
  getCountryRule,
  EMAIL_MAX_LENGTH,
  validateEmail,
  validateCompanyText,
  validateCompanyCode,
  validatePhone,
} from '../../utils/formValidation.js'

const PAGE_SIZE = 10
const COMPANY_NAME_MAX_LENGTH = 100
const COMPANY_CODE_MAX_LENGTH = 20
const COMPANY_NAME_REGEX = /^[A-Za-z0-9À-ÖØ-öø-ÿ&().,'\- ]+$/
const COMPANY_CODE_REGEX = /^[A-Za-z0-9_-]+$/

const EMPTY_FORM = {
  name: '',
  code: '',
  contact_email: '',
  contact_phone: '',
  contact_phone_country_code: '+91',
  country: '',
  status: 'TRIAL',
}

// function validateCompanyName(value) {
//   const name = value.trim()

//   if (!name) return 'Company name is required.'
//   if (name.length < 2) return 'Company name must contain at least 2 characters.'
//   if (name.length > COMPANY_NAME_MAX_LENGTH) {
//     return `Company name must not exceed ${COMPANY_NAME_MAX_LENGTH} characters.`
//   }
//   if (!COMPANY_NAME_REGEX.test(name)) {
//     return 'Company name contains unsupported characters.'
//   }

//   return ''
// }

export default function CompaniesPage() {
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')

  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [touched, setTouched] = useState({})
  const [fieldErrors, setFieldErrors] = useState({})

  const [confirm, setConfirm] = useState(null)



  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.listCompanies({
        search: search || undefined,
        offset,
        limit: PAGE_SIZE,
        ordering: `${sortOrder === 'desc' ? '-' : ''}${sortBy}`,
      })
      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load companies')
    } finally {
      setLoading(false)
    }
  }, [search, offset, sortBy, sortOrder])

  useEffect(() => {
    load()
  }, [load])

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
    setOffset(0)
  }

  const handleSearch = (value) => {
    setSearch(value)
    setOffset(0)
  }

  const updateField = (field, value) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }))

    setTouched((prev) => ({
      ...prev,
      [field]: true,
    }))

    let message = ''

    if (field === 'name') {message = validateCompanyText(value, 'Company name')}
    if (field === 'code') {message = validateCompanyCode(value)}
    if (field === 'contact_email') message = validateEmail(value)
    if (field === 'contact_phone') {message = validatePhone(value, form.country)}
    if (field === 'country') {message = value ? '' : 'Please select a country.'}
    if (field === 'status') {message = value ? '' : 'Please select a status.'}

    setFieldErrors((prev) => ({
      ...prev,
      [field]: message,
    }))
  }

  const handleCountryChange = (country) => {
    const selected = COUNTRY_OPTIONS.find((item) => item.value === country)

    setForm((prev) => ({
      ...prev,
      country,
      contact_phone_country_code: selected?.dialCode || '',
    }))

    const phoneError = validatePhone(form.contact_phone, country)

    setTouched((prev) => ({
      ...prev,
      country: true,
      contact_phone: true,
    }))

    setFieldErrors((prev) => ({
      ...prev,
      country: country ? '' : 'Please select a country.',
      contact_phone: phoneError,
    }))
  }

  const isFormValid = () => {
    const errors = {
      name: validateCompanyText(form.name, 'Company name'),
      code: validateCompanyCode(form.code),
      contact_email: validateEmail(form.contact_email),
      country: form.country ? '' : 'Please select a country.',
      contact_phone: validatePhone(form.contact_phone, form.country),
      status: form.status ? '' : 'Please select a status.',
    }

    setTouched({
      name: true,
      code: true,
      contact_email: true,
      country: true,
      contact_phone: true,
      status: true,
    })

    setFieldErrors(errors)

    return !Object.values(errors).some(Boolean)
  }

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setTouched({})
    setFieldErrors({})
    setCreateOpen(true)
  }

  const closeCreate = () => {
    setCreateOpen(false)
    setForm(EMPTY_FORM)
    setTouched({})
    setFieldErrors({})
  }

  const handleCreate = async () => {
    if (!isFormValid()) {
      return
    }

    setSaving(true)
    try {
      const created = await superadminApi.createCompany({
        ...form,
        name: form.name.trim(),
        code: form.code.trim(),
        contact_email: form.contact_email.trim().toLowerCase(),
        contact_phone: form.contact_phone.trim(),
      })
      addToast('Company created successfully')
      closeCreate()
      setOffset(0)
      load()
      navigate(`/admin/companies/${created.id}`)
     } catch (err) {
    console.error('Create company failed:', err)

    const hasFieldError = applyBackendFieldErrors(err)

    if (!hasFieldError) {
      const message =
        err?.payload?.detail ||
        err?.payload?.message ||
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Failed to create company.'

      addToast(message, 'error')
    }
  } finally {
      setSaving(false)
    }
  }

  const applyBackendFieldErrors = (err) => {
  const source =
    err?.payload?.errors ||
    err?.payload?.field_errors ||
    err?.payload?.data?.errors ||
    err?.payload?.data?.field_errors ||
    err?.payload?.data ||
    err?.payload ||
    err?.response?.data?.errors ||
    err?.response?.data?.field_errors ||
    err?.response?.data?.data?.errors ||
    err?.response?.data?.data?.field_errors ||
    err?.response?.data?.data ||
    err?.response?.data ||
    {}

  const allowedFields = [
    'name',
    'code',
    'contact_email',
    'country',
    'contact_phone',
    'status',
  ]

  const mapped = {}

  for (const field of allowedFields) {
    const value = source?.[field]

    if (value !== undefined && value !== null) {
      mapped[field] = Array.isArray(value)
        ? value.join(' ')
        : String(value)
    }
  }

  if (Object.keys(mapped).length > 0) {
    setFieldErrors((prev) => ({
      ...prev,
      ...mapped,
    }))

    setTouched((prev) => {
      const next = { ...prev }

      Object.keys(mapped).forEach((field) => {
        next[field] = true
      })

      return next
    })

    return true
  }

  return false
}

  const runAction = async (action, company) => {
    setConfirm(null)
    try {
      await action(company)
      addToast('Action completed successfully')
      load()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Action failed', 'error')
    }
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <button onClick={() => navigate(`/admin/companies/${row.id}`)} className="font-medium text-[var(--color-primary)] hover:underline">
          {row.name}
        </button>
      ),
    },
    { key: 'code', header: 'Code' },
    { key: 'contact_email', header: 'Email', render: (row) => <span className="text-[var(--color-ink-soft)]">{row.contact_email || '—'}</span> },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: 'user_count',
      header: 'Employees',
      render: (row) => <span className="text-[var(--color-ink-soft)]">{row.user_count ?? 0}</span>,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => <span className="text-[var(--color-muted)]">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button onClick={() => navigate(`/admin/companies/${row.id}`)} className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
            View
          </button>
          {row.status === 'SUSPENDED' ? (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.activateCompany(row.id), company: row, label: 'Activate' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Activate
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.suspendCompany(row.id), company: row, label: 'Suspend' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
            >
              Suspend
            </button>
          )}
          {row.is_deleted ? (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.restoreCompany(row.id), company: row, label: 'Restore' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Restore
            </button>
          ) : (
            <button
              onClick={() => setConfirm({ action: () => superadminApi.softDeleteCompany(row.id), company: row, label: 'Delete' })}
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
            >
              Delete
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <AdminLayout title="Companies" breadcrumb="Companies">
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
          title="Companies"
          subtitle="Manage all client companies across the platform."
          actions={
            <Button onClick={openCreate}>Create Company</Button>
          }
        />

        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox value={search} onChange={handleSearch} placeholder="Search companies..." />
            <span className="text-xs text-[var(--color-muted)]">{count} result{count !== 1 ? 's' : ''}</span>
          </div>

          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            error={error}
            onRetry={load}
            emptyTitle="No companies found"
            emptyDescription="Try adjusting your search or create a new company."
          />

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button intent="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </Button>
              <span className="text-sm text-[var(--color-muted)]">
                Page {currentPage} of {totalPages}
              </span>
              <Button intent="secondary" size="sm" disabled={offset + PAGE_SIZE >= count} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          )}
        </Card>

        {/* Sort hint */}
        <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
          <button onClick={() => toggleSort('name')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by name
          </button>
          <span>·</span>
          <button onClick={() => toggleSort('created_at')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by created
          </button>
          <span>·</span>
          <button onClick={() => toggleSort('status')} className="font-medium text-[var(--color-primary)] hover:underline">
            Sort by status
          </button>
        </div>
      </div>

      {/* Create Company Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={closeCreate} />
          <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
            <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">Create Company</h3>
            <div className="mt-4 flex flex-col gap-4">
              <div>
                <Input
                  label="Name"
                  value={form.name}
                  maxLength={COMPANY_NAME_MAX_LENGTH}
                  onChange={(e) => updateField('name', e.target.value)}
                />
                {touched.name && (
                  <p className={`mt-1 text-xs ${fieldErrors.name ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.name || '✓ Valid company name.'}
                  </p>
                )}
              </div>

              <div>
                <Input
                  label="Code"
                  value={form.code}
                  maxLength={COMPANY_CODE_MAX_LENGTH}
                  onChange={(e) => updateField('code', e.target.value)}
                />
                {touched.code && (
                  <p className={`mt-1 text-xs ${fieldErrors.code ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.code || '✓ Valid company code.'}
                  </p>
                )}
              </div>

              <div>
                <Input
                  label="Contact Email"
                  type="email"
                  value={form.contact_email}
                  maxLength={EMAIL_MAX_LENGTH}
                  onChange={(e) => updateField('contact_email', e.target.value)}
                />
                {touched.contact_email && (
                  <p className={`mt-1 text-xs ${fieldErrors.contact_email ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.contact_email || '✓ Valid email address.'}
                  </p>
                )}
              </div>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                  Country
                </span>
                <select
                  value={form.country}
                  onChange={(e) => handleCountryChange(e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select country</option>
                  {COUNTRY_OPTIONS.map((country) => (
                    <option key={country.value} value={country.value}>
                      {country.label} ({country.dialCode})
                    </option>
                  ))}
                </select>
                {touched.country && (
                  <p className={`mt-1 text-xs ${fieldErrors.country ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.country || '✓ Country selected.'}
                  </p>
                )}
              </label>

              <div>
                <div className="grid grid-cols-[110px_1fr] gap-2">
                  <Input
                    label="Code"
                    value={form.contact_phone_country_code}
                    readOnly
                    className="bg-[var(--color-canvas)]"
                  />
                  <Input
                    label="Contact Phone"
                    type="tel"
                    value={form.contact_phone}
                    maxLength={getCountryRule(form.country)?.maxDigits || 15}
                    onChange={(e) =>
                      updateField(
                        'contact_phone',
                        e.target.value.replace(/\D/g, ''),
                      )
                    }
                  />
                  {touched.contact_phone && (
                    <p className={`mt-1 text-xs ${
                      fieldErrors.contact_phone
                        ? 'text-red-600'
                        : 'text-green-600'
                    }`}>
                      {fieldErrors.contact_phone || '✓ Valid contact phone.'}
                    </p>
                  )}
                </div>
                {form.country && getCountryRule(form.country) && (
                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    Example: {getCountryRule(form.country).example} — Enter {getCountryRule(form.country).minDigits === getCountryRule(form.country).maxDigits
                      ? `exactly ${getCountryRule(form.country).minDigits}`
                      : `${getCountryRule(form.country).minDigits}-${getCountryRule(form.country).maxDigits}`} digits without the country code.
                  </p>
                )}
              </div>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => updateField('status', e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="TRIAL">Trial</option>
                  <option value="ACTIVE">Active</option>
                  <option value="SUSPENDED">Suspended</option>
                </select>
                {touched.status && (
                  <p className={`mt-1 text-xs ${fieldErrors.status ? 'text-red-600' : 'text-green-600'}`}>
                    {fieldErrors.status || '✓ Status selected.'}
                  </p>
                )}
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button intent="secondary" onClick={closeCreate}>Cancel</Button>
              <Button onClick={handleCreate} isLoading={saving}>Create</Button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirm}
        title={confirm ? `${confirm.label} company?` : ''}
        message={confirm ? `Are you sure you want to ${confirm.label.toLowerCase()} ${confirm.company.name}?` : ''}
        confirmLabel={confirm?.label}
        intent={confirm?.label === 'Delete' || confirm?.label === 'Suspend' ? 'primary' : 'primary'}
        onConfirm={() => confirm && runAction(confirm.action, confirm.company)}
        onCancel={() => setConfirm(null)}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </AdminLayout>
  )
}