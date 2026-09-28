import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient, { unwrap } from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'

const FILTERS = [
  { value: 'ALL', label: 'All Data' },
  { value: 'NOT_VALIDATED', label: 'Not Validated' },
  { value: 'VALIDATED', label: 'Validated' },
  { value: 'POSTED', label: 'Posted' },
]

function unwrapHistory(response) {
  const payload = response?.data?.data ?? response?.data ?? response ?? {}
  return {
    results: Array.isArray(payload?.results) ? payload.results : [],
    count: Number(payload?.count ?? 0),
  }
}

function statusClass(status) {
  switch (String(status || '').toUpperCase()) {
    case 'POSTED':
      return 'bg-emerald-100 text-emerald-700'
    case 'VALIDATED':
      return 'bg-blue-100 text-blue-700'
    case 'NOT_VALIDATED':
      return 'bg-red-100 text-red-700'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}

function formatDate(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString()
}

export default function DataExtractionHistoryPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('ALL')
  const [records, setRecords] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [connection, setConnection] = useState(null)

  const loadHistory = useCallback(async () => {
    try {
      setLoading(true)
      setError('')

      const params = new URLSearchParams({
        offset: '0',
        limit: '100',
      })

      if (filter !== 'ALL') {
        params.set('status', filter)
      }

      const response = await apiClient.get(
        `/ocr/history/?${params.toString()}`,
      )

      const payload = unwrapHistory(response)
      setRecords(payload.results)
      setSelectedIds(new Set())
    } catch (err) {
      console.error('Failed to load Data Extraction History:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to load Data Extraction History.',
      )
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  useEffect(() => {
    let cancelled = false

    netsuiteApi
      .getMyConnection()
      .then((payload) => {
        const data = payload?.data ?? payload ?? null
        if (!cancelled) setConnection(data)
      })
      .catch((err) => {
        console.warn('No NetSuite connection available:', err)
        if (!cancelled) setConnection(null)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const visibleSelectableRecords = useMemo(
    () => records.filter((item) => item?.document_ids?.length),
    [records],
  )

  const selectedRecords = useMemo(
    () => records.filter((item) => selectedIds.has(item?.batch_id)),
    [records, selectedIds],
  )

  const selectedDocumentIds = useMemo(
    () => [
      ...new Set(
        selectedRecords.flatMap((item) =>
          Array.isArray(item?.document_ids)
            ? item.document_ids
            : item?.document_id
              ? [item.document_id]
              : [],
        ),
      ),
    ],
    [selectedRecords],
  )

  const selectedUnvalidatedDocumentIds = useMemo(
    () => [
      ...new Set(
        selectedRecords.flatMap((item) =>
          Array.isArray(item?.unvalidated_document_ids)
            ? item.unvalidated_document_ids
            : [],
        ),
      ),
    ],
    [selectedRecords],
  )

  const allSelectedAreValidated = useMemo(
    () =>
      selectedRecords.length > 0 &&
      selectedRecords.every(
        (item) => item?.validation_status === 'VALIDATED',
      ),
    [selectedRecords],
  )

  const allVisibleSelected = useMemo(
    () =>
      visibleSelectableRecords.length > 0 &&
      visibleSelectableRecords.every((item) =>
        selectedIds.has(item.batch_id),
      ),
    [visibleSelectableRecords, selectedIds],
  )

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelectedIds(new Set())
      return
    }

    setSelectedIds(
      new Set(
        visibleSelectableRecords.map((item) => item.batch_id),
      ),
    )
  }

  const toggleRecord = (batchId) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(batchId)) {
        next.delete(batchId)
      } else {
        next.add(batchId)
      }
      return next
    })
  }

  const runBatchAction = async () => {
    if (!selectedDocumentIds.length) {
      setError('Select at least one history record first.')
      return
    }

    if (!connection?.id) {
      setError('A NetSuite connection is required before validation or posting.')
      return
    }

    try {
      setWorking(true)
      setError('')
      setNotice('')

      if (allSelectedAreValidated) {
        const queued = await netsuiteApi.batchPostDocuments(
          selectedDocumentIds,
          connection?.id || null,
        )

        const jobId = queued?.job_id
        if (!jobId) {
          throw new Error('NetSuite batch posting did not return a job ID.')
        }

        const maxAttempts = 120
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          const statusResponse = await netsuiteApi.getBatchJobStatus(jobId)
          const job = statusResponse?.data ?? statusResponse ?? {}
          const jobStatus = String(job?.status || '').toUpperCase()

          if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(jobStatus)) {
            if (jobStatus === 'SUCCESS' && Number(job?.failed || 0) === 0) {
              setNotice('✓ Selected OCR record(s) posted successfully to NetSuite.')
            } else {
              setError(
                job?.error ||
                  `${Number(job?.failed || 0)} document(s) failed to post.`,
              )
            }
            break
          }

          await new Promise((resolve) => setTimeout(resolve, 1500))
        }
      } else {
        const queued = await netsuiteApi.validateBatchDocuments(
          selectedUnvalidatedDocumentIds,
          connection?.id || null,
        )

        const jobId = queued?.job_id
        if (!jobId) {
          throw new Error('NetSuite batch validation did not return a job ID.')
        }

        const maxAttempts = 120
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          const statusResponse = await netsuiteApi.getBatchJobStatus(jobId)
          const job = statusResponse?.data ?? statusResponse ?? {}
          const jobStatus = String(job?.status || '').toUpperCase()

          if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(jobStatus)) {
            if (jobStatus === 'SUCCESS') {
              setNotice('✓ Selected OCR record(s) were validated again.')
            } else {
              setError(job?.error || 'Batch validation failed.')
            }
            break
          }

          await new Promise((resolve) => setTimeout(resolve, 1500))
        }
      }

      await loadHistory()
    } catch (err) {
      console.error('Data Extraction History action failed:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'The OCR history action failed.',
      )
    } finally {
      setWorking(false)
    }
  }

  return (
    <ClientLayout
      title="Data Extraction History"
      breadcrumb="OCR / Data Extraction / Data Extraction History"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
                Data Extraction History
              </h1>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Review single OCR files and multiple-file batches, validate unresolved records, and post only fully validated records to NetSuite.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                disabled={working}
                className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]"
              >
                {FILTERS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <Button
                type="button"
                intent="secondary"
                onClick={toggleSelectAll}
                disabled={working || !visibleSelectableRecords.length}
              >
                {allVisibleSelected ? 'Clear All' : 'Select All'}
              </Button>

              <Button
                type="button"
                onClick={runBatchAction}
                disabled={working || !selectedDocumentIds.length}
                isLoading={working}
              >
                {allSelectedAreValidated ? 'Post to NetSuite' : 'Refresh'}
              </Button>
            </div>
          </div>

          {error && (
            <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {notice && (
            <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {notice}
            </div>
          )}
        </Card>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-8 text-sm text-[var(--color-muted)]">
              Loading history...
            </div>
          ) : records.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">
                No records found.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[760px]">
                <div className="grid grid-cols-[44px_1.6fr_120px_120px_170px_130px] border-b border-[var(--color-border)] bg-[var(--color-canvas)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  <div />
                  <div>File / Batch</div>
                  <div>Type</div>
                  <div>Files</div>
                  <div>Created</div>
                  <div>Status</div>
                </div>

                <div className="divide-y divide-[var(--color-border)]">
                  {records.map((item) => {
                    const selected = selectedIds.has(item.batch_id)
                    const isPosted = item.validation_status === 'POSTED'

                    return (
                      <div
                        key={item.batch_id}
                        className={`grid grid-cols-[44px_1.6fr_120px_120px_170px_130px] items-center px-4 py-4 ${selected ? 'bg-[var(--color-primary-soft)]' : ''}`}
                      >
                        <div>
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleRecord(item.batch_id)}
                            disabled={working || isPosted}
                            aria-label={`Select ${item.filename || 'OCR record'}`}
                          />
                        </div>

                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-[var(--color-ink)]">
                            {item.filename || 'OCR Record'}
                          </p>
                          <p className="mt-1 text-xs text-[var(--color-muted)]">
                            {item.type === 'batch'
                              ? `${item.validated_count || 0}/${item.file_count} validated`
                              : 'Single file'}
                          </p>
                        </div>

                        <div className="text-sm text-[var(--color-muted)]">
                          {item.type === 'batch' ? 'Batch' : 'Single'}
                        </div>

                        <div className="text-sm text-[var(--color-ink)]">
                          {item.file_count}
                        </div>

                        <div className="text-sm text-[var(--color-muted)]">
                          {formatDate(item.created_at)}
                        </div>

                        <div className="flex flex-col items-start gap-2">
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClass(item.validation_status)}`}
                          >
                            {item.validation_status || 'NOT VALIDATED'}
                          </span>

                          {item.type === 'batch' ? (
                            <Button
                              type="button"
                              intent="secondary"
                              onClick={() =>
                                navigate(`/app/ocr/history/batch/${item.batch_id}`)
                              }
                            >
                              View Result
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              intent="secondary"
                              onClick={() =>
                                navigate(`/app/ocr/history/${item.document_id}`)
                              }
                            >
                              View Result
                            </Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
