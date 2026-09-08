import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const PAGE_SIZE = 20

const EMPTY_FORM = {
  tran_id: '',
  tran_date: '',
  entity: '',
  name: '',
  invoice: '',
  amount: '',
}

export default function TransactionsPage() {
  const [searchParams] = useSearchParams()

  const transactionType = searchParams.get('transaction_type') || ''
  const recordType = searchParams.get('record_type') || ''

  const title = recordType || 'Transactions'

  const [rows, setRows] = useState([])
  const [count, setCount] = useState(0)
  const [offset, setOffset] = useState(0)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [newOpen, setNewOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const loadTransactions = useCallback(async () => {
    if (!transactionType || !recordType) {
      setRows([])
      setCount(0)
      setError('Transaction type and record type are required.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await clientApi.getTransactions({
        transaction_type: transactionType,
        record_type: recordType,
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

  useEffect(() => {
    setOffset(0)
  }, [transactionType, recordType])

  useEffect(() => {
    loadTransactions()
  }, [loadTransactions])

  const hasPrevious = offset > 0
  const hasNext = offset + rows.length < count

const openNewForm = () => {
  const today = new Date()
  const day = String(today.getDate()).padStart(2, '0')
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const year = today.getFullYear()

  setForm({
    ...EMPTY_FORM,
    tran_date: `${day}/${month}/${year}`,
  })
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

  const handleCreate = async (event) => {
    event.preventDefault()

    if (!transactionType || !recordType) {
      setError('Transaction type and record type are required.')
      return
    }

    const dateParts = form.tran_date.split('/')

    if (
      dateParts.length !== 3 ||
      dateParts[0].length !== 2 ||
      dateParts[1].length !== 2 ||
      dateParts[2].length !== 4
    ) {
      setError('Tran Date must be in DD/MM/YYYY format.')
      return
    }

    setSaving(true)
    setError('')

    try {
      const [day,month,year] = form.tran_date.split('/')
      const payload = {
        ...form,
        tran_date: `${year}-${month}-${day}`,
      }

      await clientApi.createTransaction({
        transactionType,
        recordType,
        payload,
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
              disabled={!transactionType || !recordType}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
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
                  {[
                    'Tran ID',
                    'Tran Date',
                    'Entity',
                    'Name',
                    'Invoice',
                    'Amount',
                  ].map((label) => (
                    <th
                      key={label}
                      className="px-4 py-3 text-left font-medium text-[var(--color-muted)]"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-10 text-center text-[var(--color-muted)]"
                    >
                      Loading transactions…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-10 text-center text-[var(--color-muted)]"
                    >
                      No transactions found.
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-[var(--color-border)] last:border-0"
                    >
                      <td className="px-4 py-3 font-medium text-[var(--color-ink)]">
                        {row.tran_id || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {row.tran_date || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink)]">
                        {row.entity || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-ink)]">
                        {row.name || '—'}
                      </td>

                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {row.invoice || '—'}
                      </td>

                      <td className="px-4 py-3 font-medium text-[var(--color-ink)]">
                        {row.amount ?? '—'}
                      </td>
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
                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Tran ID
                    </label>

                    <input
                      type="text"
                      value={form.tran_id}
                      onChange={(event) =>
                        updateField('tran_id', event.target.value)
                      }
                      required
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Tran Date
                    </label>

                    <input
                      type="text"
                      value={form.tran_date}
                      onChange={(event) =>
                        updateField('tran_date', event.target.value)
                      }
                      placeholder="DD/MM/YYYY"
                      required
                      inputMode="numeric"
                      maxLength={10}
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Entity
                    </label>

                    <input
                      type="text"
                      value={form.entity}
                      onChange={(event) =>
                        updateField('entity', event.target.value)
                      }
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Name
                    </label>

                    <input
                      type="text"
                      value={form.name}
                      onChange={(event) =>
                        updateField('name', event.target.value)
                      }
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Invoice
                    </label>

                    <input
                      type="text"
                      value={form.invoice}
                      onChange={(event) =>
                        updateField('invoice', event.target.value)
                      }
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-sm font-medium text-[var(--color-ink)]">
                      Amount
                    </label>

                    <input
                      type="number"
                      step="0.01"
                      value={form.amount}
                      onChange={(event) =>
                        updateField('amount', event.target.value)
                      }
                      required
                      className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    />
                  </div>
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