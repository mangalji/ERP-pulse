import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const PAGE_SIZE = 20

const EMPTY_FORM = {}

const TRANSACTION_ROUTES = new Set(['/app/transaction', '/app/transactions'])

function collectTransactionContexts(items, contexts = []) {
  ;(items || []).forEach((item) => {
    const queryParams = item?.query_params || {}
    const transactionType = String(queryParams.transaction_type || '').trim()
    const recordType = String(queryParams.record_type || '').trim()

    if (TRANSACTION_ROUTES.has(item?.route) && transactionType) {
      contexts.push({ transactionType, recordType })
    }

    collectTransactionContexts(item?.children, contexts)
  })

  return contexts
}

export default function TransactionsPage() {
  const [searchParams] = useSearchParams()

  const transactionType = searchParams.get('transaction_type') || ''
  const recordType = searchParams.get('record_type') || ''

  const title = recordType || transactionType || 'Transactions'

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [schema, setSchema] = useState({ fields: [] })
  const [navigationItems, setNavigationItems] = useState([])
  const [navigationLoading, setNavigationLoading] = useState(true)
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
  } catch {
    setSchema({ fields: [] })
  }
}, [])

useEffect(() => {
  loadSchema()
}, [loadSchema])

  useEffect(() => {
    const loadTransactionContexts = async () => {
      try {
        const menu = await clientApi.getNavigationMenu()
        setNavigationItems(Array.isArray(menu) ? menu : [])
      } catch {
        setNavigationItems([])
      } finally {
        setNavigationLoading(false)
      }
    }

    loadTransactionContexts()
  }, [])

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

    // A Level-3 navigation item already identifies the transaction context.
    // At higher levels, these remain empty so the user can choose them.
    initialForm.transaction_type = transactionType
    initialForm.record_type = recordType
    
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
      ...(field === 'transaction_type' && current.transaction_type !== value
        ? { record_type: '' }
        : {}),
    }))
  }

  const tableFields = schema.fields || []
  const transactionContexts = collectTransactionContexts(navigationItems)
  const transactionTypeOptions = [...new Set([
    ...transactionContexts.map((context) => context.transactionType),
    transactionType,
  ].filter(Boolean))]
  const selectedFormTransactionType = String(form.transaction_type || '').trim()
  const recordTypeOptions = [...new Set([
    ...transactionContexts
      .filter((context) => context.transactionType === selectedFormTransactionType)
      .map((context) => context.recordType),
    selectedFormTransactionType === transactionType ? recordType : '',
  ].filter(Boolean))]

  const formFields = tableFields.filter(
    (field) =>
      !field.read_only &&
      field.name !== 'company',
  )

  const handleCreate = async (event) => {
    event.preventDefault()

    const selectedTransactionType = String(
      form.transaction_type || transactionType,
    ).trim()
    const selectedRecordType = String(
      form.record_type || recordType,
    ).trim()

    if (!selectedTransactionType || !selectedRecordType) {
      setError('Transaction type and record type are required.')
      return
    }

    const {
      transaction_type: _transactionType,
      record_type: _recordType,
      ...transactionPayload
    } = form

    setSaving(true)
    setError('')

    try {
      await clientApi.createTransaction({
        transactionType: selectedTransactionType,
        recordType: selectedRecordType,
        payload: transactionPayload,
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
            <button
              type="button"
              onClick={openNewForm}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
            >
              New
            </button>
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
                    New {recordType || 'Transaction'}
                  </h2>

                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    {transactionType && recordType
                      ? `${transactionType} / ${recordType}`
                      : 'Choose a transaction type and record type.'}
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

                    if (field.name === 'transaction_type' || field.name === 'record_type') {
                      const isTransactionType = field.name === 'transaction_type'
                      const options = isTransactionType
                        ? transactionTypeOptions
                        : recordTypeOptions
                      const isDisabled = navigationLoading ||
                        (!isTransactionType && !selectedFormTransactionType)

                      return (
                        <div key={field.name}>
                          <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                            {field.label}
                          </label>
                          <select
                            value={value}
                            onChange={(event) => updateField(field.name, event.target.value)}
                            required={field.required}
                            disabled={isDisabled}
                            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <option value="">
                              {navigationLoading
                                ? 'Loading options…'
                                : isTransactionType
                                  ? 'Select transaction type'
                                  : 'Select record type'}
                            </option>
                            {options.map((option) => (
                              <option key={option} value={option}>{option}</option>
                            ))}
                          </select>
                        </div>
                      )
                    }
                  
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
