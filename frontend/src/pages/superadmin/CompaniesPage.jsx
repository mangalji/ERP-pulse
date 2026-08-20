import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import DataTable from '../../components/superadmin/DataTable.jsx'
import SearchBox from '../../components/superadmin/SearchBox.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import ConfirmDialog from '../../components/superadmin/ConfirmDialog.jsx'
import Card from '../../components/ui/Card.jsx'
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

const EMPTY_FORM = {
  name: '',
  code: '',
  contact_email: '',
  contact_phone: '',
  contact_phone_country_code: '+91',
  country: '',
  industry: '',
  company_size: '',
  city: '',
  status: 'TRIAL',
}

export default function CompaniesPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { toasts, addToast, removeToast } = useToast()

  // ─────────────────────────────────────────────────────────────
  // Active / normal companies
  // ─────────────────────────────────────────────────────────────
  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [sortBy, setSortBy] = useState('name')
  const [sortOrder, setSortOrder] = useState('asc')

  // ─────────────────────────────────────────────────────────────
  // Soft deleted companies
  // ─────────────────────────────────────────────────────────────
  const [softDeletedRows, setSoftDeletedRows] = useState([])
  const [softDeletedCount, setSoftDeletedCount] = useState(0)
  const [softDeletedOffset, setSoftDeletedOffset] = useState(0)
  const [softDeletedLoading, setSoftDeletedLoading] = useState(true)
  const [softDeletedError, setSoftDeletedError] = useState(null)

  // ─────────────────────────────────────────────────────────────
  // Permanently deleted companies
  // ─────────────────────────────────────────────────────────────
  const [permanentlyDeletedRows, setPermanentlyDeletedRows] = useState([])
  const [permanentlyDeletedCount, setPermanentlyDeletedCount] = useState(0)
  const [permanentlyDeletedOffset, setPermanentlyDeletedOffset] = useState(0)
  const [permanentlyDeletedLoading, setPermanentlyDeletedLoading] = useState(true)
  const [permanentlyDeletedError, setPermanentlyDeletedError] = useState(null)

  // ─────────────────────────────────────────────────────────────
  // Create company
  // ─────────────────────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [touched, setTouched] = useState({})
  const [fieldErrors, setFieldErrors] = useState({})

  // ─────────────────────────────────────────────────────────────
  // Confirmation dialog
  // ─────────────────────────────────────────────────────────────
  const [confirm, setConfirm] = useState(null)

  // ─────────────────────────────────────────────────────────────
  // Load active companies
  // ─────────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await superadminApi.listCompanies({
        search: search || undefined,
        scope: 'active',
        offset,
        limit: PAGE_SIZE,
        ordering: `${sortOrder === 'desc' ? '-' : ''}${sortBy}`,
      })

      setRows(data.results || [])
      setCount(data.count || 0)
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.payload?.detail ||
          err?.message ||
          'Failed to load companies'
      )
    } finally {
      setLoading(false)
    }
  }, [search, offset, sortBy, sortOrder])

  // ─────────────────────────────────────────────────────────────
  // Load soft-deleted companies
  // ─────────────────────────────────────────────────────────────
  const loadSoftDeleted = useCallback(async () => {
    setSoftDeletedLoading(true)
    setSoftDeletedError(null)

    try {
      const data = await superadminApi.listCompanies({
        scope: 'soft_deleted',
        offset: softDeletedOffset,
        limit: PAGE_SIZE,
      })

      setSoftDeletedRows(data.results || [])
      setSoftDeletedCount(data.count || 0)
    } catch (err) {
      setSoftDeletedError(
        err?.payload?.message ||
          err?.payload?.detail ||
          err?.message ||
          'Failed to load soft-deleted companies'
      )
    } finally {
      setSoftDeletedLoading(false)
    }
  }, [softDeletedOffset])

  // ─────────────────────────────────────────────────────────────
  // Load permanently deleted companies
  // ─────────────────────────────────────────────────────────────
  const loadPermanentlyDeleted = useCallback(async () => {
    setPermanentlyDeletedLoading(true)
    setPermanentlyDeletedError(null)

    try {
      const data = await superadminApi.permanentlyDeletedCompanies({
        offset: permanentlyDeletedOffset,
        limit: PAGE_SIZE,
      })

      setPermanentlyDeletedRows(data.results || [])
      setPermanentlyDeletedCount(data.count || 0)
    } catch (err) {
      setPermanentlyDeletedError(
        err?.payload?.message ||
          err?.payload?.detail ||
          err?.message ||
          'Failed to load permanently deleted companies'
      )
    } finally {
      setPermanentlyDeletedLoading(false)
    }
  }, [permanentlyDeletedOffset])

  // ─────────────────────────────────────────────────────────────
  // Effects
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    loadSoftDeleted()
  }, [loadSoftDeleted])

  useEffect(() => {
    loadPermanentlyDeleted()
  }, [loadPermanentlyDeleted])

  // ─────────────────────────────────────────────────────────────
  // Pre-fill company form from Demo Request navigation state
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const prefill = location.state?.prefillCompany
    if (!prefill) {
      return
    }
    setForm({
      ...EMPTY_FORM,
      name: prefill.name || '',
      contact_email: prefill.contact_email || '',
      contact_phone: prefill.contact_phone || '',
      country: prefill.country || '',
      industry: prefill.industry || '',
      company_size: prefill.company_size || '',
      city: prefill.city || '',
    })
    setCreateOpen(true)
    // Clear state to prevent duplicate prefill on refresh
    navigate(location.pathname, { replace: true })
  }, [location.state, location.pathname, navigate])

  // ─────────────────────────────────────────────────────────────
  // Sorting
  // ─────────────────────────────────────────────────────────────
  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }

    setOffset(0)
  }

  // ─────────────────────────────────────────────────────────────
  // Search
  // ─────────────────────────────────────────────────────────────
  const handleSearch = (value) => {
    setSearch(value)
    setOffset(0)
  }

  // ─────────────────────────────────────────────────────────────
  // Form field validation
  // ─────────────────────────────────────────────────────────────
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

    if (field === 'name') {
      message = validateCompanyText(value, 'Company name')
    }

    if (field === 'code') {
      message = validateCompanyCode(value)
    }

    if (field === 'contact_email') {
      message = validateEmail(value)
    }

    if (field === 'contact_phone') {
      message = validatePhone(value, form.country)
    }

    if (field === 'country') {
      message = value ? '' : 'Please select a country.'
    }

    if (field === 'status') {
      message = value ? '' : 'Please select a status.'
    }

    setFieldErrors((prev) => ({
      ...prev,
      [field]: message,
    }))
  }

  // ─────────────────────────────────────────────────────────────
  // Country change
  // ─────────────────────────────────────────────────────────────
  const handleCountryChange = (country) => {
    const selected = COUNTRY_OPTIONS.find(
      (item) => item.value === country
    )

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

  // ─────────────────────────────────────────────────────────────
  // Validate entire create form
  // ─────────────────────────────────────────────────────────────
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

  // ─────────────────────────────────────────────────────────────
  // Create modal
  // ─────────────────────────────────────────────────────────────
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

  // ─────────────────────────────────────────────────────────────
  // Map backend validation errors to individual fields
  // ─────────────────────────────────────────────────────────────
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

  // ─────────────────────────────────────────────────────────────
  // Create company
  // ─────────────────────────────────────────────────────────────
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

      await load()
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

  // ─────────────────────────────────────────────────────────────
  // Generic company action
  // ─────────────────────────────────────────────────────────────
  const runAction = async (action, company) => {
    setConfirm(null)

    try {
      await action(company)

      addToast('Action completed successfully')

      await Promise.all([
        load(),
        loadSoftDeleted(),
        loadPermanentlyDeleted(),
      ])
    } catch (err) {
      addToast(
        err?.payload?.detail ||
          err?.payload?.message ||
          err?.message ||
          'Action failed',
        'error'
      )
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Pagination
  // ─────────────────────────────────────────────────────────────
  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const softDeletedTotalPages = Math.ceil(
    softDeletedCount / PAGE_SIZE
  )
  const softDeletedCurrentPage =
    Math.floor(softDeletedOffset / PAGE_SIZE) + 1

  const permanentlyDeletedTotalPages = Math.ceil(
    permanentlyDeletedCount / PAGE_SIZE
  )
  const permanentlyDeletedCurrentPage =
    Math.floor(permanentlyDeletedOffset / PAGE_SIZE) + 1

  // ─────────────────────────────────────────────────────────────
  // Normal companies columns
  // ─────────────────────────────────────────────────────────────
  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <button
          onClick={() =>
            navigate(`/admin/companies/${row.id}`)
          }
          className="font-medium text-[var(--color-primary)] hover:underline"
        >
          {row.name}
        </button>
      ),
    },
    {
      key: 'code',
      header: 'Code',
    },
    {
      key: 'contact_email',
      header: 'Email',
      render: (row) => (
        <span className="text-[var(--color-ink-soft)]">
          {row.contact_email || '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <StatusBadge status={row.status} />
      ),
    },
    {
      key: 'user_count',
      header: 'Employees',
      render: (row) => (
        <span className="text-[var(--color-ink-soft)]">
          {row.user_count ?? 0}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => (
        <span className="text-[var(--color-muted)]">
          {row.created_at
            ? new Date(row.created_at).toLocaleDateString()
            : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() =>
              navigate(`/admin/companies/${row.id}`)
            }
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
          >
            View
          </button>

          {row.status === 'SUSPENDED' ? (
            <button
              onClick={() =>
                setConfirm({
                  action: () =>
                    superadminApi.activateCompany(row.id),
                  company: row,
                  label: 'Activate',
                })
              }
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
            >
              Activate
            </button>
          ) : (
            <button
              onClick={() =>
                setConfirm({
                  action: () =>
                    superadminApi.suspendCompany(row.id),
                  company: row,
                  label: 'Suspend',
                })
              }
              className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-netsuite)] hover:bg-[var(--color-netsuite-soft)]"
            >
              Suspend
            </button>
          )}

          <button
            onClick={() =>
              setConfirm({
                action: () =>
                  superadminApi.softDeleteCompany(row.id),
                company: row,
                label: 'Delete',
              })
            }
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]"
          >
            Delete
          </button>
        </div>
      ),
    },
  ]

  // ─────────────────────────────────────────────────────────────
  // Soft deleted columns
  // ─────────────────────────────────────────────────────────────
  const softDeletedColumns = [
    {
      key: 'name',
      header: 'Company',
      render: (row) => (
        <span className="font-medium text-[var(--color-ink)]">
          {row.name}
        </span>
      ),
    },
    {
      key: 'code',
      header: 'Code',
    },
    {
      key: 'status',
      header: 'Status',
      render: () => (
        <StatusBadge status="SUSPENDED" />
      ),
    },
    {
      key: 'deleted_at',
      header: 'Deleted',
      render: (row) => (
        <span className="text-[var(--color-muted)]">
          {row.deleted_at
            ? new Date(row.deleted_at).toLocaleDateString()
            : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() =>
              setConfirm({
                action: () =>
                  superadminApi.restoreCompany(row.id),
                company: row,
                label: 'Restore',
              })
            }
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]"
          >
            Restore
          </button>
        </div>
      ),
    },
  ]

  // ─────────────────────────────────────────────────────────────
  // Permanently deleted columns
  // ─────────────────────────────────────────────────────────────
  const permanentlyDeletedColumns = [
    {
      key: 'company_name',
      header: 'Company',
      render: (row) => (
        <span className="font-medium text-[var(--color-ink)]">
          {row.company_name || '—'}
        </span>
      ),
    },
    {
      key: 'company_code',
      header: 'Code',
      render: (row) => row.company_code || '—',
    },
    {
      key: 'status',
      header: 'Status',
      render: () => (
        <StatusBadge status="SUSPENDED" />
      ),
    },
    {
      key: 'soft_deleted_at',
      header: 'Soft Deleted',
      render: (row) => (
        <span className="text-[var(--color-muted)]">
          {row.soft_deleted_at
            ? new Date(
                row.soft_deleted_at
              ).toLocaleDateString()
            : '—'}
        </span>
      ),
    },
    {
      key: 'permanently_deleted_at',
      header: 'Permanent Delete',
      render: (row) => (
        <span className="text-[var(--color-muted)]">
          {row.permanently_deleted_at
            ? new Date(
                row.permanently_deleted_at
              ).toLocaleDateString()
            : '—'}
        </span>
      ),
    },
    {
      key: 'lifecycle_status',
      header: 'Lifecycle',
      render: () => (
        <span className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium bg-[var(--color-negative-soft)] text-[var(--color-negative)]">
          Permanently Deleted
        </span>
      ),
    },
  ]

  return (
    <AdminLayout
      title="Companies"
      breadcrumb="Companies"
    >
      <div className="flex flex-col gap-6">
        {/* Back / breadcrumb */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin')}
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
            Dashboard
          </span>
        </div>

        {/* Header */}
        <PageHeader
          title="Companies"
          subtitle="Manage all client companies across the platform."
          actions={
            <Button onClick={openCreate}>
              Create Company
            </Button>
          }
        />

        {/* ─────────────────────────────────────────────────────── */}
        {/* Active / Trial / Suspended Companies */}
        {/* ─────────────────────────────────────────────────────── */}
        <Card className="p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <SearchBox
              value={search}
              onChange={handleSearch}
              placeholder="Search active companies..."
            />

            <span className="text-xs text-[var(--color-muted)]">
              {count} result{count !== 1 ? 's' : ''}
            </span>
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
              <Button
                intent="secondary"
                size="sm"
                disabled={offset === 0}
                onClick={() =>
                  setOffset((value) =>
                    Math.max(0, value - PAGE_SIZE)
                  )
                }
              >
                Previous
              </Button>

              <span className="text-sm text-[var(--color-muted)]">
                Page {currentPage} of {totalPages}
              </span>

              <Button
                intent="secondary"
                size="sm"
                disabled={
                  offset + PAGE_SIZE >= count
                }
                onClick={() =>
                  setOffset(
                    (value) => value + PAGE_SIZE
                  )
                }
              >
                Next
              </Button>
            </div>
          )}
        </Card>

        {/* ─────────────────────────────────────────────────────── */}
        {/* Soft Deleted Companies */}
        {/* ─────────────────────────────────────────────────────── */}
        <Card className="p-5">
          <div className="mb-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-ink)]">
                  Soft Deleted Companies
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Companies deleted within the 15-day recovery period.
                </p>
              </div>

              <span className="text-xs text-[var(--color-muted)]">
                {softDeletedCount} result
                {softDeletedCount !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <DataTable
            columns={softDeletedColumns}
            rows={softDeletedRows}
            loading={softDeletedLoading}
            error={softDeletedError}
            onRetry={loadSoftDeleted}
            emptyTitle="No soft-deleted companies"
            emptyDescription="Companies deleted within the recovery period will appear here."
          />

          {softDeletedTotalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button
                intent="secondary"
                size="sm"
                disabled={softDeletedOffset === 0}
                onClick={() =>
                  setSoftDeletedOffset((value) =>
                    Math.max(0, value - PAGE_SIZE)
                  )
                }
              >
                Previous
              </Button>

              <span className="text-sm text-[var(--color-muted)]">
                Page {softDeletedCurrentPage} of{' '}
                {softDeletedTotalPages}
              </span>

              <Button
                intent="secondary"
                size="sm"
                disabled={
                  softDeletedOffset + PAGE_SIZE >=
                  softDeletedCount
                }
                onClick={() =>
                  setSoftDeletedOffset(
                    (value) => value + PAGE_SIZE
                  )
                }
              >
                Next
              </Button>
            </div>
          )}
        </Card>

        {/* ─────────────────────────────────────────────────────── */}
        {/* Permanently Deleted Companies */}
        {/* ─────────────────────────────────────────────────────── */}
        <Card className="p-5">
          <div className="mb-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-[var(--color-ink)]">
                  Permanently Deleted Companies
                </h2>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Historical records of companies permanently removed after the 15-day recovery period.
                </p>
              </div>

              <span className="text-xs text-[var(--color-muted)]">
                {permanentlyDeletedCount} result
                {permanentlyDeletedCount !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <DataTable
            columns={permanentlyDeletedColumns}
            rows={permanentlyDeletedRows}
            loading={permanentlyDeletedLoading}
            error={permanentlyDeletedError}
            onRetry={loadPermanentlyDeleted}
            emptyTitle="No permanently deleted companies"
            emptyDescription="Permanent deletion history will appear here."
          />

          {permanentlyDeletedTotalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <Button
                intent="secondary"
                size="sm"
                disabled={
                  permanentlyDeletedOffset === 0
                }
                onClick={() =>
                  setPermanentlyDeletedOffset(
                    (value) =>
                      Math.max(0, value - PAGE_SIZE)
                  )
                }
              >
                Previous
              </Button>

              <span className="text-sm text-[var(--color-muted)]">
                Page {permanentlyDeletedCurrentPage} of{' '}
                {permanentlyDeletedTotalPages}
              </span>

              <Button
                intent="secondary"
                size="sm"
                disabled={
                  permanentlyDeletedOffset +
                    PAGE_SIZE >=
                  permanentlyDeletedCount
                }
                onClick={() =>
                  setPermanentlyDeletedOffset(
                    (value) => value + PAGE_SIZE
                  )
                }
              >
                Next
              </Button>
            </div>
          )}
        </Card>

        {/* Sort hint */}
        <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
          <button
            onClick={() => toggleSort('name')}
            className="font-medium text-[var(--color-primary)] hover:underline"
          >
            Sort by name
          </button>

          <span>·</span>

          <button
            onClick={() => toggleSort('created_at')}
            className="font-medium text-[var(--color-primary)] hover:underline"
          >
            Sort by created
          </button>

          <span>·</span>

          <button
            onClick={() => toggleSort('status')}
            className="font-medium text-[var(--color-primary)] hover:underline"
          >
            Sort by status
          </button>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────── */}
      {/* Create Company Modal */}
      {/* ───────────────────────────────────────────────────────── */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={closeCreate}
          />

          <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl">
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-5">
              <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Create Company
              </h3>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-6 pb-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Company name */}
                <div>
                  <Input
                    label="Name"
                    value={form.name}
                    maxLength={COMPANY_NAME_MAX_LENGTH}
                    onChange={(e) =>
                      updateField(
                        'name',
                        e.target.value
                      )
                    }
                  />

                  {touched.name && (
                    <p
                      className={`mt-1 text-xs ${
                        fieldErrors.name
                          ? 'text-red-600'
                          : 'text-green-600'
                      }`}
                    >
                      {fieldErrors.name ||
                        '✓ Valid company name.'}
                    </p>
                  )}
                </div>

                {/* Company code */}
                <div>
                  <Input
                    label="Code"
                    value={form.code}
                    maxLength={COMPANY_CODE_MAX_LENGTH}
                    onChange={(e) =>
                      updateField(
                        'code',
                        e.target.value
                      )
                    }
                  />

                  {touched.code && (
                    <p
                      className={`mt-1 text-xs ${
                        fieldErrors.code
                          ? 'text-red-600'
                          : 'text-green-600'
                      }`}
                    >
                      {fieldErrors.code ||
                        '✓ Valid company code.'}
                    </p>
                  )}
                </div>

                {/* Email */}
                <div>
                  <Input
                    label="Contact Email"
                    type="email"
                    value={form.contact_email}
                    maxLength={EMAIL_MAX_LENGTH}
                    onChange={(e) =>
                      updateField(
                        'contact_email',
                        e.target.value
                      )
                    }
                  />

                  {touched.contact_email && (
                    <p
                      className={`mt-1 text-xs ${
                        fieldErrors.contact_email
                          ? 'text-red-600'
                          : 'text-green-600'
                      }`}
                    >
                      {fieldErrors.contact_email ||
                        '✓ Valid email address.'}
                    </p>
                  )}
                </div>

                {/* Country */}
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                    Country
                  </span>

                  <select
                    value={form.country}
                    onChange={(e) =>
                      handleCountryChange(
                        e.target.value
                      )
                    }
                    className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                  >
                    <option value="">
                      Select country
                    </option>

                    {COUNTRY_OPTIONS.map((country) => (
                      <option
                        key={country.value}
                        value={country.value}
                      >
                        {country.label} (
                        {country.dialCode})
                      </option>
                    ))}
                  </select>

                  {touched.country && (
                    <p
                      className={`mt-1 text-xs ${
                        fieldErrors.country
                          ? 'text-red-600'
                          : 'text-green-600'
                      }`}
                    >
                      {fieldErrors.country ||
                        '✓ Country selected.'}
                    </p>
                  )}
                </label>

                {/* Phone - full width */}
                <div className="sm:col-span-2">
                  <div className="grid grid-cols-[110px_1fr] gap-2">
                    <Input
                      label="Code"
                      value={
                        form.contact_phone_country_code
                      }
                      readOnly
                      className="bg-[var(--color-canvas)]"
                    />

                    <Input
                      label="Contact Phone"
                      type="tel"
                      value={form.contact_phone}
                      maxLength={
                        getCountryRule(form.country)
                          ?.maxDigits || 15
                      }
                      onChange={(e) =>
                        updateField(
                          'contact_phone',
                          e.target.value.replace(
                            /\D/g,
                            ''
                          )
                        )
                      }
                    />

                    {touched.contact_phone && (
                      <p
                        className={`col-span-2 mt-1 text-xs ${
                          fieldErrors.contact_phone
                            ? 'text-red-600'
                            : 'text-green-600'
                        }`}
                      >
                        {fieldErrors.contact_phone ||
                          '✓ Valid contact phone.'}
                      </p>
                    )}
                  </div>

                  {form.country &&
                    getCountryRule(form.country) && (
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        Example:{' '}
                        {getCountryRule(form.country).example}
                        {' — '}
                        Enter{' '}
                        {getCountryRule(form.country).minDigits ===
                        getCountryRule(form.country).maxDigits
                          ? `exactly ${getCountryRule(form.country).minDigits}`
                          : `${getCountryRule(form.country).minDigits}-${getCountryRule(form.country).maxDigits}`}
                        {' '}digits without the country code.
                      </p>
                    )}
                </div>

                {/* Industry */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Industry
                    </span>
                    <select
                      value={form.industry}
                      onChange={(e) =>
                        updateField('industry', e.target.value)
                      }
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    >
                      <option value="">Select industry</option>
                      <option value="TECHNOLOGY">Technology</option>
                      <option value="MANUFACTURING">Manufacturing</option>
                      <option value="RETAIL">Retail</option>
                      <option value="FINANCE">Finance</option>
                      <option value="HEALTHCARE">Healthcare</option>
                      <option value="LOGISTICS">Logistics</option>
                      <option value="ECOMMERCE">E-commerce</option>
                      <option value="SERVICES">Professional Services</option>
                      <option value="OTHER">Other</option>
                    </select>
                  </label>
                </div>

                {/* Company Size */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Company Size
                    </span>
                    <select
                      value={form.company_size}
                      onChange={(e) =>
                        updateField('company_size', e.target.value)
                      }
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    >
                      <option value="">Select size</option>
                      <option value="1-10">1-10 employees</option>
                      <option value="11-50">11-50 employees</option>
                      <option value="51-200">51-200 employees</option>
                      <option value="201-500">201-500 employees</option>
                      <option value="500+">500+ employees</option>
                    </select>
                  </label>
                </div>

                {/* City */}
                <div>
                  <Input
                    label="City"
                    value={form.city}
                    onChange={(e) =>
                      updateField('city', e.target.value)
                    }
                  />
                </div>

                {/* Status */}
                <div>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium text-[var(--color-ink-soft)]">
                      Status
                    </span>

                    <select
                      value={form.status}
                      onChange={(e) =>
                        updateField(
                          'status',
                          e.target.value
                        )
                      }
                      className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                    >
                      <option value="TRIAL">
                        Trial
                      </option>

                      <option value="ACTIVE">
                        Active
                      </option>

                      <option value="SUSPENDED">
                        Suspended
                      </option>
                    </select>

                    {touched.status && (
                      <p
                        className={`mt-1 text-xs ${
                          fieldErrors.status
                            ? 'text-red-600'
                            : 'text-green-600'
                        }`}
                      >
                        {fieldErrors.status ||
                          '✓ Status selected.'}
                      </p>
                    )}
                  </label>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="flex-shrink-0 border-t border-[var(--color-border)] px-6 py-4">
              <div className="flex justify-end gap-2">
                <Button
                  intent="secondary"
                  onClick={closeCreate}
                >
                  Cancel
                </Button>

                <Button
                  onClick={handleCreate}
                  isLoading={saving}
                >
                  Create
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation dialog */}
      <ConfirmDialog
        open={!!confirm}
        title={
          confirm
            ? `${confirm.label} company?`
            : ''
        }
        message={
          confirm
            ? `Are you sure you want to ${confirm.label.toLowerCase()} ${confirm.company.name}?`
            : ''
        }
        confirmLabel={confirm?.label}
        intent="primary"
        onConfirm={() =>
          confirm &&
          runAction(
            confirm.action,
            confirm.company
          )
        }
        onCancel={() => setConfirm(null)}
      />

      <Toast
        toasts={toasts}
        removeToast={removeToast}
      />
    </AdminLayout>
  )
}