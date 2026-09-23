import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const PAGE_SIZE = 20

const EMPTY_FORM = {}

export default function TransactionsPage() {
  const [searchParams] = useSearchParams()

  const queryParams = Object.fromEntries(searchParams.entries())
  const queryParamEntries = Object.entries(queryParams)

  const transactionType = queryParamEntries[0]?.[1] || ''
  const recordType = queryParamEntries[1]?.[1] || ''

  const hasProductContext = Boolean(transactionType && recordType)

  const title = recordType || transactionType || 'Transactions'

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [schema, setSchema] = useState({ fields: [] })
  const [offset, setOffset] = useState(0)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [newOpen, setNewOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const loadTransactions = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const response = await clientApi.getTransactions({
        ...(transactionType ? { transaction_type: transactionType } : {}),
        ...(recordType ? { record_type: recordType } : {}),
        limit: PAGE_SIZE,
        offset,
      })

      const results = Array.isArray(response)
        ? response
        : (response?.results || [])

      setRows(results)
      setCount(Number(response?.count ?? results.length))
    } catch (err) {
      const message =
        err?.response?.data?.message ||
        err?.response?.data?.detail ||
        'Failed to load transactions.'

      setRows([])
      setCount(0)
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [transactionType, recordType, offset])

  const loadSchema = useCallback(async () => {
  try {
    const response = await clientApi.getTransactions({
      schema: 'true',
    })

    setSchema(response || { fields: [] })
  } catch (err) {
    setSchema({ fields: [] })
  }
}, [])

useEffect(() => {
  loadSchema()
}, [loadSchema])

  useEffect(() => {
    setOffset(0)
  }, [transactionType, recordType])

  useEffect(() => {
    loadTransactions()
  }, [loadTransactions])

  const hasPrevious = offset > 0
  const hasNext = offset + rows.length < count

  const openNewForm = () => {
    const initialForm = {}

    formFields.forEach((field) => {
      if (field.name === 'tran_date') {
        initialForm[field.name] = new Date().toISOString().slice(0, 10)
      } else if (field.default !== undefined && field.default !== null) {
        initialForm[field.name] = field.default
      } else {
        initialForm[field.name] = ''
      }
    })
    
    setForm(initialForm)
    setError('')
    setNewOpen(true)
  }

  const closeNewForm = () => {
    if (saving) {
      return
    }

    setNewOpen(false)
    setForm(EMPTY_FORM)
  }

  const updateField = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  const tableFields = schema.fields || []

  const formFields = tableFields.filter(
    (field) =>
      !field.read_only &&
      !['company', 'transaction_type', 'record_type'].includes(field.name),
  )

  const handleCreate = async (event) => {
    event.preventDefault()

    if (!transactionType || !recordType) {
      setError('Transaction type and record type are required.')
      return
    }

    setSaving(true)
    setError('')

    try {
      await clientApi.createTransaction({
        transactionType,
        recordType,
        payload:form,
      })

      setNewOpen(false)
      setForm(EMPTY_FORM)
      setOffset(0)

      await loadTransactions()
    } catch (err) {
      const message =
        err?.response?.data?.message ||
        err?.response?.data?.detail ||
        'Failed to create transaction.'

      setError(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <ClientLayout
      title={title}
      breadcrumb={`Transaction / ${title}`}
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-ink)]">
              {title}
            </h1>

            <p className="mt-1 text-sm text-[var(--color-muted)]">
              {transactionType
                ? `${transactionType} / ${recordType}`
                : 'Transaction data'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-sm text-[var(--color-muted)]">
              {count} record{count === 1 ? '' : 's'}
            </div>
            {hasProductContext && (
              <button
                type="button"
                onClick={openNewForm}
                className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
              >
                New
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="border-b border-[var(--color-border)] bg-[var(--color-background)]">
                <tr>
                  {tableFields.map((field) => (
                    <th
                      key={field.name}
                      className="px-4 py-3 text-left font-medium text-[var(--color-muted)]"
                    >
                      {field.label}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={Math.max(tableFields.length, 1)}
                      className="px-4 py-10 text-center text-[var(--color-muted)]"
                    >
                      Loading transactions…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={Math.max(tableFields.length, 1)}
                      className="px-4 py-10 text-center text-[var(--color-muted)]"
                    >
                      No transactions found.
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-[var(--color-border)] last:border-0">
                      {tableFields.map((field) => (
                      <td
                        key={field.name}
                        className="px-4 py-3 text-[var(--color-ink)]"
                      >
                        {row[field.name] ?? '—'}
                      </td>
                    ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-[var(--color-border)] px-4 py-3">
            <span className="text-xs text-[var(--color-muted)]">
              {count === 0
                ? '0'
                : `${offset + 1}–${Math.min(
                    offset + rows.length,
                    count,
                  )}`}{' '}
              of {count}
            </span>

            <div className="flex gap-2">
              <button
                type="button"
                disabled={!hasPrevious || loading}
                onClick={() =>
                  setOffset((current) =>
                    Math.max(0, current - PAGE_SIZE),
                  )
                }
                className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                Previous
              </button>

              <button
                type="button"
                disabled={!hasNext || loading}
                onClick={() =>
                  setOffset((current) => current + PAGE_SIZE)
                }
                className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {newOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
            <div className="w-full max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl">
              <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
                <div>
                  <h2 className="text-lg font-semibold text-[var(--color-ink)]">
                    New {recordType}
                  </h2>

                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    {transactionType} / {recordType}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={closeNewForm}
                  disabled={saving}
                  className="text-sm text-[var(--color-muted)] hover:text-[var(--color-ink)] disabled:opacity-50"
                >
                  Close
                </button>
              </div>

              <form onSubmit={handleCreate} className="space-y-5 p-5">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {formFields.map((field) => {
                    const value = form[field.name] ?? ''
                  
                    let inputType = 'text'
                  
                    if (field.type === 'DateField') {
                      inputType = 'date'
                    } else if (field.type === 'DecimalField' || field.type === 'IntegerField') {
                      inputType = 'number'
                    }
                  
                    return (
                      <div key={field.name}>
                        <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                          {field.label}
                        </label>
                    
                        <input
                          type={inputType}
                          value={value}
                          onChange={(event) =>
                            updateField(field.name, event.target.value)
                          }
                          required={field.required}
                          step={inputType === 'number' ? 'any' : undefined}
                          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                        />
                      </div>
                    )
                  })}
                </div>

                <div className="flex justify-end gap-3 border-t border-[var(--color-border)] pt-4">
                  <button
                    type="button"
                    onClick={closeNewForm}
                    disabled={saving}
                    className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm disabled:opacity-50"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ClientLayout>
  )
}