import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import apiClient from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import NetSuiteReauthBanner from '../../components/netsuite/NetSuiteReauthBanner.jsx'
import {
  isCompanyAdminUser,
  isNetSuiteReauthError,
  isNetSuiteReauthJob,
} from '../../utils/netsuiteErrors.js'
import { formatDateTime } from '../../utils/formatDate.js'

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
  return Number.isNaN(date.getTime()) ? '--' : formatDateTime(date)
}

function historyRecordLabel(record) {
  const historyNumber = record?.history_number
  const identifier = historyNumber ? `History #${historyNumber}` : 'History record'
  return `${identifier} — ${record?.filename || 'Unnamed OCR file'}`
}

function errorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.error ||
    error?.message ||
    'The requested action failed.'
  )
}
// function isCompanyAdminUser(user) {
//   if (user?.is_superadmin || user?.is_staff) return true

//   return (Array.isArray(user?.roles) ? user.roles : []).some((role) => {
//     const value =
//       typeof role === 'string'
//         ? role
//         : role?.name ?? role?.code ?? role?.key ?? ''

//     return ['company_admin', 'company admin'].includes(
//       String(value).trim().toLowerCase(),
//     )
//   })
// }

export default function DataExtractionHistoryPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canDeleteHistory = isCompanyAdminUser(user)
  const [filter, setFilter] = useState('ALL')
  const [records, setRecords] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [deletingSelected, setDeletingSelected] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [actionMessages, setActionMessages] = useState([])
  const [reauthRequired, setReauthRequired] = useState(false)
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
    () => records.filter((item) => item?.validation_status != 'POSTED'),
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

  const handleDelete = async (item) => {
    if (!canDeleteHistory) return

    const recordId = item?.type === 'batch' ? item?.batch_id : item?.upload_id
    if (!recordId) {
      setError('This history record cannot be deleted because its ID is missing.')
      return
    }

    try {
      setDeletingId(item.batch_id)
      setError('')
      setNotice('')
      setActionMessages([])

      const recordType = item?.type === 'batch' ? 'batch' : 'upload'
      await apiClient.delete(
        `/ocr/history/uploads/${recordId}/?record_type=${recordType}`,
      )

      setActionMessages([
        {
          tone: 'success',
          text: `${historyRecordLabel(item)}: deleted successfully.`,
        },
      ])
      setRecords((current) =>
        current.filter((record) => record.batch_id !== item.batch_id),
      )
      setSelectedIds((current) => {
        const next = new Set(current)
        next.delete(item.batch_id)
        return next
      })
    } catch (err) {
      console.error('Failed to delete OCR history record:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to delete the OCR history record.',
      )
    } finally {
      setDeletingId(null)
    }
  }

  const handleDeleteSelected = async () => {
    if (!canDeleteHistory || !selectedRecords.length) return

    const targets = selectedRecords
      .map((item) => ({
        id: item?.type === 'batch' ? item?.batch_id : item?.upload_id,
        record_type: item?.type === 'batch' ? 'batch' : 'upload',
        historyId: item?.batch_id,
      }))
      .filter((item) => item.id)

    if (!targets.length) {
      setError('The selected history records cannot be deleted because an ID is missing.')
      return
    }

    try {
      setDeletingSelected(true)
      setError('')
      setNotice('')
      setActionMessages([])
      await apiClient.delete('/ocr/history/bulk/', {
        data: {
          records: targets.map(({ id, record_type }) => ({ id, record_type })),
        },
      })

      const deletedHistoryIds = new Set(targets.map((item) => item.historyId))
      setRecords((current) =>
        current.filter((record) => !deletedHistoryIds.has(record.batch_id)),
      )
      setSelectedIds((current) => {
        const next = new Set(current)
        deletedHistoryIds.forEach((id) => next.delete(id))
        return next
      })
      setActionMessages(
        selectedRecords.map((record) => ({
          tone: 'success',
          text: `${historyRecordLabel(record)}: deleted successfully.`,
        })),
      )
    } catch (err) {
      console.error('Failed to delete selected OCR history records:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Unable to delete the selected OCR history records.',
      )
    } finally {
      setDeletingSelected(false)
    }
  }
  const waitForBatchJob = async (jobId) => {
  const maxAttempts = 120

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const statusResponse = await netsuiteApi.getBatchJobStatus(jobId)
    const job = statusResponse?.data ?? statusResponse ?? {}
    const jobStatus = String(job?.status || '').toUpperCase()

    if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(jobStatus)) {
      return job
    }

    await new Promise((resolve) => setTimeout(resolve, 1500))
  }

  throw new Error('NetSuite batch job timed out.')
}

  const runBatchAction = async () => {
    if (!selectedRecords.length) {
      setError('Select at least one history record first.')
      return
    }

    if (!connection?.id) {
      setError('A NetSuite connection is required before validation or posting.')
      return
    }

    const recordByDocumentId = new Map()
    selectedRecords.forEach((record) => {
      const documentIds = Array.isArray(record?.document_ids)
        ? record.document_ids
        : record?.document_id
          ? [record.document_id]
          : []
      documentIds.forEach((documentId) => {
        recordByDocumentId.set(String(documentId), record)
      })
    })

    const labelForDocument = (documentId) =>
      historyRecordLabel(recordByDocumentId.get(String(documentId)))

    const addBatchResultMessages = (results, action, successStatuses, messages) => {
      results.forEach((result) => {
        const succeeded = successStatuses.includes(
          String(result?.status || '').toUpperCase(),
        )
        const reason = result?.error ||
          (Array.isArray(result?.errors) && result.errors.length
            ? result.errors.join('; ')
            : result?.status || 'Unknown error')

        messages.push({
          tone: succeeded ? 'success' : 'error',
          text: succeeded
            ? `${labelForDocument(result?.document_id)}: ${action} successfully.`
            : `${labelForDocument(result?.document_id)}: ${action} failed — ${reason}`,
        })
      })
    }

    try {
      setWorking(true)
      setError('')
      setReauthRequired(false)
      setNotice('')
      setActionMessages([])

      const messages = []
      const singleRecords = selectedRecords.filter(
        (item) => item?.type !== 'batch',
      )
      const batchRecords = selectedRecords.filter(
        (item) => item?.type === 'batch',
      )

      if (allSelectedAreValidated) {
        const singleDocumentIds = [
          ...new Set(singleRecords.map((item) => item?.document_id).filter(Boolean)),
        ]
        const batchDocumentIds = [
          ...new Set(batchRecords.flatMap((item) => item?.document_ids || [])),
        ]

        if (batchDocumentIds.length) {
          const queued = await netsuiteApi.batchPostDocuments(batchDocumentIds, connection.id)
          if (!queued?.job_id) {
            throw new Error('NetSuite batch posting did not return a job ID.')
          }

          const job = await waitForBatchJob(queued.job_id)
          if (isNetSuiteReauthJob(job)) setReauthRequired(true)
          const results = Array.isArray(job?.results) ? job.results : []
          addBatchResultMessages(results, 'posted to NetSuite', ['POSTED', 'ALREADY_POSTED'], messages)
          if (!results.length) {
            batchRecords.forEach((record) => {
              messages.push({
                tone: 'error',
                text: `${historyRecordLabel(record)}: posting failed — ${job?.error || 'No result was returned.'}`,
              })
            })
          }
        }

        for (const documentId of singleDocumentIds) {
          try {
            await netsuiteApi.postOCRVendorBill(documentId, connection.id)
            messages.push({ tone: 'success', text: `${labelForDocument(documentId)}: posted to NetSuite successfully.` })
          } catch (err) {
            if (isNetSuiteReauthError(err)) setReauthRequired(true)
            messages.push({ tone: 'error', text: `${labelForDocument(documentId)}: posting failed — ${errorMessage(err)}` })
          }
        }
      } else {
        const singleValidationIds = [
          ...new Set(
            singleRecords.flatMap((item) =>
              Array.isArray(item?.unvalidated_document_ids)
                ? item.unvalidated_document_ids
                : item?.document_id
                  ? [item.document_id]
                  : [],
            ).filter(Boolean),
          ),
        ]
        const batchValidationIds = [
          ...new Set(batchRecords.flatMap((item) => item?.unvalidated_document_ids || [])),
        ]

        if (batchValidationIds.length) {
          const queued = await netsuiteApi.validateBatchDocuments(batchValidationIds, connection.id)
          if (!queued?.job_id) {
            throw new Error('NetSuite batch validation did not return a job ID.')
          }

          const job = await waitForBatchJob(queued.job_id)
          if (isNetSuiteReauthJob(job)) setReauthRequired(true)
          const results = Array.isArray(job?.results) ? job.results : []
          addBatchResultMessages(results, 'validated', ['VALIDATED'], messages)
          if (!results.length) {
            batchRecords.forEach((record) => {
              messages.push({
                tone: 'error',
                text: `${historyRecordLabel(record)}: validation failed — ${job?.error || 'No result was returned.'}`,
              })
            })
          }
        }

        for (const documentId of singleValidationIds) {
          try {
            await netsuiteApi.validateDocument(documentId, connection.id)
            messages.push({ tone: 'success', text: `${labelForDocument(documentId)}: validated successfully.` })
          } catch (err) {
            if (isNetSuiteReauthError(err)) setReauthRequired(true)
            messages.push({ tone: 'error', text: `${labelForDocument(documentId)}: validation failed — ${errorMessage(err)}` })
          }
        }
      }

      setActionMessages(messages)
      await loadHistory()
    } catch (err) {
      console.error('Data Extraction History action failed:', err)
      if (isNetSuiteReauthError(err)) setReauthRequired(true)
      const reason = errorMessage(err)
      setActionMessages(selectedRecords.map((record) => ({
        tone: 'error',
        text: `${historyRecordLabel(record)}: action failed — ${reason}`,
      })))
    } finally {
      setWorking(false)
    }
  }

  return (
    <ClientLayout
      title="Data Extraction History"
      breadcrumb="OCR / Data Extraction / Data Extraction History"
    >
      <div className="flex w-full flex-col gap-6">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
                Data Extraction History
              </h1>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Review single OCR files and multiple-file batches, validate unresolved records, and post only fully validated records to NetSuite.
              </p>
            </div>

             <div className="flex shrink-0 flex-wrap items-center gap-2">
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
                disabled={working || deletingId || deletingSelected || !visibleSelectableRecords.length}
              >
                {allVisibleSelected ? 'Clear All' : 'Select All'}
              </Button>

              {canDeleteHistory && selectedRecords.length > 0 && (
                <button
                  type="button"
                  onClick={handleDeleteSelected}
                  disabled={working || deletingId || deletingSelected}
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {deletingSelected
                    ? 'Deleting selected...'
                    : `Delete Selected (${selectedRecords.length})`}
                </button>
              )}

              <Button
                type="button"
                onClick={runBatchAction}
                disabled={working || deletingId || deletingSelected || !selectedDocumentIds.length}
                isLoading={working}
              >
                {allSelectedAreValidated ? 'Post to NetSuite' : 'Refresh'}
              </Button>
            </div>
          </div>

          {reauthRequired && (
            <div className="mt-5">
              <NetSuiteReauthBanner connectionId={connection?.id} />
            </div>
          )}
          {error && !reauthRequired && (
            <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {notice && (
            <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {notice}
            </div>
          )}

          {actionMessages.length > 0 && (
            <div className="mt-5 max-h-72 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
              <p className="mb-3 text-sm font-semibold text-[var(--color-ink)]">
                Operation results
              </p>
              <ul className="space-y-2 text-sm">
                {actionMessages.map((message, index) => (
                  <li
                    key={`${message.text}-${index}`}
                    className={`rounded-md border px-3 py-2 ${
                      message.tone === 'error'
                        ? 'border-red-200 bg-red-50 text-red-700'
                        : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    }`}
                  >
                    {message.text}
                  </li>
                ))}
              </ul>
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
              <div className="min-w-[1240px]">
                <div className="grid grid-cols-[44px_100px_1.35fr_90px_70px_150px_150px_120px_140px_56px] border-b border-[var(--color-border)] bg-[var(--color-canvas)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  <div />
                  <div>History #</div>
                  <div>File / Batch</div>
                  <div>Type</div>
                  <div>Files</div>
                  <div>Created By</div>
                  <div>Created</div>
                  <div>Status</div>
                  <div>NetSuite Bill</div>
                  <div className="text-center">{canDeleteHistory ? 'Action' : ''}</div>
                </div>

                <div className="divide-y divide-[var(--color-border)]">
                  {records.map((item) => {
                    const selected = selectedIds.has(item.batch_id)
                    const isPosted = item.validation_status === 'POSTED'
                    const netsuiteRecords = Array.isArray(item.netsuite_records)
                      ? item.netsuite_records
                      : []

                    return (
                      <div
                        key={item.batch_id}
                        className={`grid grid-cols-[44px_100px_1.35fr_90px_70px_150px_150px_120px_140px_56px] items-center px-4 py-4 ${selected ? 'bg-[var(--color-primary-soft)]' : ''}`}
                      >
                        <div>
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleRecord(item.batch_id)}
                            disabled={working || deletingId || deletingSelected || isPosted}
                            aria-label={`Select ${item.filename || 'OCR record'}`}
                          />
                        </div>

                        <div className="font-mono text-sm font-semibold text-[var(--color-ink)]">
                          #{item.history_number || '--'}
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

                        <div
                          className="truncate pr-2 text-sm text-[var(--color-muted)]"
                          title={item.owner_name || ''}
                        >
                          {item.owner_name || '--'}
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

                        <div className="flex max-h-24 flex-col gap-2 overflow-y-auto">
                          {netsuiteRecords.length ? netsuiteRecords.map((record) => (
                            <div key={record.document_id} className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs text-[var(--color-ink)]" title={`NetSuite Internal ID ${record.internal_id}`}>
                                #{record.internal_id}
                              </span>
                              {record.url && (
                                <button
                                  type="button"
                                  onClick={() => window.open(record.url, '_blank', 'noopener,noreferrer')}
                                  className="rounded-md border border-[var(--color-border)] px-2 py-1 text-xs font-semibold text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
                                >
                                  View
                                </button>
                              )}
                            </div>
                          )) : '--'}
                        </div>

                        <div className="flex items-center justify-center">
                          {canDeleteHistory && (
                            <button
                              type="button"
                              onClick={() => handleDelete(item)}
                              disabled={working || deletingId || deletingSelected}
                              aria-label={`Delete ${item.filename || 'OCR history record'}`}
                              title="Delete"
                              className="rounded-md p-2 text-[var(--color-negative)] transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {deletingId === item.batch_id ? (
                                <svg
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.8"
                                  className="h-4 w-4 animate-spin"
                                >
                                  <circle cx="12" cy="12" r="9" className="opacity-25" />
                                  <path d="M21 12a9 9 0 0 1-9 9" />
                                </svg>
                              ) : (
                                <svg
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.8"
                                  className="h-4 w-4"
                                >
                                  <path d="M4 7h16" />
                                  <path d="M10 11v6M14 11v6" />
                                  <path d="M6 7l1 13h10l1-13" />
                                  <path d="M9 7V4h6v3" />
                                </svg>
                              )}
                            </button>
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
