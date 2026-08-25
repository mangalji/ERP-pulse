import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient, { unwrap } from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import { useToast } from '../../components/ui/Toast.jsx'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import OcrReviewWorkspace from '../../components/ocr/OcrReviewWorkspace.jsx'
import ExtractionConfigPanel from '../../components/ocr/ExtractionConfigPanel.jsx'

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
  'image/bmp',
  'image/tiff',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'text/plain',
]

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff,.docx,.xlsx,.csv,.txt,application/pdf,image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain'
const MAX_FILE_SIZE = 10 * 1024 * 1024
const MAX_FILES = 20

function createPreview(file) {
  if (!file) return null
  return URL.createObjectURL(file)
}

function isImage(file) {
  return file?.type?.startsWith('image/')
}

function isPdf(file) {
  return file?.type === 'application/pdf' || /\.pdf$/i.test(file?.name || '')
}

function isDocx(file) {
  return (
    file?.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    /\.docx$/i.test(file?.name || '')
  )
}

function isSpreadsheet(file) {
  return (
    file?.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    /\.xlsx$/i.test(file?.name || '')
  )
}

function isCsv(file) {
  return (
    file?.type === 'text/csv' ||
    file?.type === 'application/csv' ||
    /\.csv$/i.test(file?.name || '')
  )
}

function isText(file) {
  return (
    file?.type === 'text/plain' ||
    /\.txt$/i.test(file?.name || '')
  )
}

function getFileCategory(file) {
  if (isPdf(file)) return 'PDF'
  if (isDocx(file)) return 'DOCX'
  if (isImage(file)) return 'Image'
  if (isSpreadsheet(file)) return 'Spreadsheet'
  if (isCsv(file)) return 'CSV'
  if (isText(file)) return 'Text'
  return 'Document'
}


export default function OcrTestPage() {

  const clearSelectedFilesAfterExtraction = useCallback(() => {
    setSelectedFiles((current) => {
      current.forEach(({ previewUrl }) => {
        if (previewUrl) {
          try {
            URL.revokeObjectURL(previewUrl)
          } catch {
            // Ignore object URL cleanup errors.
          }
        }
      })
      return []
    })
    setActiveIndex(0)
  }, [])

  const waitForBatchJob = useCallback(async (jobId) => {
    if (!jobId) {
      throw new Error('Batch operation was created without a job ID.')
    }

    const startedAt = Date.now()
    const maxPollingMs = 30 * 60 * 1000

    while (Date.now() - startedAt < maxPollingMs) {
      const response = await apiClient.get(
        `/netsuite/ocr/batch/jobs/${jobId}/`,
      )

      const job = unwrap(response) || {}
      const status = String(job?.status || '').toUpperCase()

      if (['SUCCESS', 'FAILURE', 'REVOKED'].includes(status)) {
        return job
      }

      await new Promise((resolve) => setTimeout(resolve, 1500))
    }

    throw new Error('Batch operation timed out after 30 minutes.')
  }, [])

  const navigate = useNavigate()
  const inputRef = useRef(null)
  const { addToast } = useToast()

  const [selectedFiles, setSelectedFiles] = useState([])
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [results, setResults] = useState([])
  const [activeIndex, setActiveIndex] = useState(0)

  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyCount, setHistoryCount] = useState(0)

  const [recentHistory, setRecentHistory] = useState([])
  const [recentHistoryLoading, setRecentHistoryLoading] = useState(true)
  const [recentHistoryError, setRecentHistoryError] = useState('')
  const [recentHistoryOffset, setRecentHistoryOffset] = useState(0)
  const [recentHistoryCount, setRecentHistoryCount] = useState(0)

  const HISTORY_PAGE_SIZE = 10

  const [dragActive, setDragActive] = useState(false)
  const [remotePreviewUrl, setRemotePreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')

  const [extractionConfig, setExtractionConfig] = useState(null)

  const [validationFilter, setValidationFilter] = useState('all')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [connection, setConnection] = useState(null)
  const [validationResult, setValidationResult] = useState(null)

  const filteredHistory = useMemo(() => {
    if (validationFilter === 'correct') {
      return history.filter(item => item.validation_status === 'VALIDATED')
    }
    if (validationFilter === 'incorrect') {
      return history.filter(item => item.validation_status === 'VALIDATION_FAILED')
    }
    return history
  }, [history, validationFilter])

  const selectableHistory = useMemo(
    () => filteredHistory.filter((item) => item?.status === 'COMPLETED'),
    [filteredHistory],
  )

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((current) => {
      const visibleIds = new Set(
        selectableHistory
          .map((item) => item?.document_id || item?.upload_id)
          .filter(Boolean),
      )
      if (visibleIds.size > 0 && [...visibleIds].every((id) => current.has(id))) {
        const next = new Set(current)
        visibleIds.forEach((id) => next.delete(id))
        return next
      }
      return new Set([...current, ...visibleIds])
    })
  }, [selectableHistory])

  const toggleSelect = useCallback((id) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const allVisibleSelected = useMemo(() => {
    const visibleIds = selectableHistory
      .map((item) => item?.document_id || item?.upload_id)
      .filter(Boolean)
    return visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))
  }, [selectableHistory, selectedIds])

  const selectedHistoryItems = useMemo(
    () =>
      filteredHistory.filter((item) => {
        const id = item?.document_id || item?.upload_id
        return id && selectedIds.has(id)
      }),
    [filteredHistory, selectedIds],
  )

  const selectedValidateIds = useMemo(
    () =>
      selectedHistoryItems
        .filter(
          (item) =>
            item.status === 'COMPLETED' &&
            item.document_id &&
            item.validation_status !== 'VALIDATED',
        )
        .map((item) => item.document_id),
    [selectedHistoryItems],
  )

  const selectedCompletedItems = useMemo(
    () =>
      selectedHistoryItems.filter(
        (item) => item?.status === 'COMPLETED',
      ),
    [selectedHistoryItems],
  )

  const handlePostSelected = async () => {
    const notSaved = selectedCompletedItems.filter(
      (item) => !item?.document_id,
    )

    const notValidated = selectedCompletedItems.filter(
      (item) =>
        item?.document_id &&
        item?.validation_status !== 'VALIDATED',
    )

    if (notSaved.length) {
      setError(
        'Save the selected OCR results before posting. ' +
          `${notSaved.length} selected file(s) are not saved yet.`,
      )
      return
    }

    if (notValidated.length) {
      setError(
        'Validate the selected OCR files before posting. ' +
          `${notValidated.length} selected file(s) are not validated yet.`,
      )
      return
    }

    if (!selectedPostIds.length) {
      setError('No selected completed files are ready to post.')
      return
    }

    await handleBatchPost(selectedPostIds)
  }

  const selectedPostIds = useMemo(
    () =>
      selectedHistoryItems
        .filter(
          (item) =>
            item.status === 'COMPLETED' &&
            item.document_id &&
            item.validation_status === 'VALIDATED',
        )
        .map((item) => item.document_id),
    [selectedHistoryItems],
  )

  // const refreshOcrHistory = useCallback(async () => {
  //   await Promise.all([
  //     loadHistory(historyOffset),
  //     loadRecentHistory(recentHistoryOffset),
  //   ])
  // }, [loadHistory, loadRecentHistory, historyOffset, recentHistoryOffset])

  const handleBatchValidate = async (ids = [...selectedValidateIds]) => {
    if (!ids.length) {
      setError('Select at least one completed document that needs validation.')
      return
    }

    try {
      setProcessing(true)
      setError('')

      const response = await apiClient.post(
        '/netsuite/ocr/batch/validate/',
        {
          document_ids: ids,
        },
      )

      const queued = unwrap(response) || {}
      const job = await waitForBatchJob(
        queued?.job_id || queued?.id,
      )

      const failedCount = Number(
        job?.failed_count ??
          job?.result?.failed_count ??
          0,
      )
      const completedCount = Number(
        job?.completed_count ??
          job?.successful_count ??
          job?.result?.completed_count ??
          0,
      )

      if (String(job?.status || '').toUpperCase() !== 'SUCCESS') {
        setError(
          job?.error ||
            job?.detail ||
            'Batch validation did not complete successfully.',
        )
      } else if (failedCount > 0) {
        setError(`${failedCount} document(s) failed validation.`)
      } else {
        addToast(
          completedCount
            ? `Batch validation completed for ${completedCount} document(s).`
            : 'Batch validation completed.',
          'success',
        )
      }

      setSelectedIds(new Set())
      await refreshOcrHistory()
    } catch (err) {
      console.error('Batch validation job failed:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Batch validation failed.',
      )
    } finally {
      setProcessing(false)
    }
  }

  const handleBatchPost = async (ids = [...selectedPostIds]) => {
    if (!ids.length) {
      setError('Select at least one validated document to post.')
      return
    }

    try {
      setProcessing(true)
      setError('')

      const response = await apiClient.post(
        '/netsuite/ocr/batch/post/',
        {
          document_ids: ids,
        },
      )

      const queued = unwrap(response) || {}
      const job = await waitForBatchJob(
        queued?.job_id || queued?.id,
      )

      const failedCount = Number(
        job?.failed_count ??
          job?.result?.failed_count ??
          0,
      )
      const completedCount = Number(
        job?.completed_count ??
          job?.successful_count ??
          job?.result?.completed_count ??
          0,
      )

      if (String(job?.status || '').toUpperCase() !== 'SUCCESS') {
        setError(
          job?.error ||
            job?.detail ||
            'Batch posting did not complete successfully.',
        )
      } else if (failedCount > 0) {
        setError(`${failedCount} document(s) failed to post.`)
      } else {
        addToast(
          completedCount
            ? `Batch posting completed for ${completedCount} document(s).`
            : 'Batch posting completed.',
          'success',
        )
      }

      setSelectedIds(new Set())
      await refreshOcrHistory()
    } catch (err) {
      console.error('Batch posting job failed:', err)
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Batch posting failed.',
      )
    } finally {
      setProcessing(false)
    }
  }

  const fetchHistoryPage = useCallback(async (offset = 0, status = null) => {
    const numericOffset = Number(offset)
    const safeOffset = Number.isFinite(numericOffset)
      ? Math.max(0, Math.floor(numericOffset))
      : 0

    const params = new URLSearchParams({
      offset: String(safeOffset),
      limit: String(HISTORY_PAGE_SIZE),
    })

    if (status) params.set('status', status)

    const response = await apiClient.get(`/ocr/history/?${params.toString()}`)
    const payload = response?.data?.data ?? response?.data ?? {}
    const items = Array.isArray(payload)
      ? payload
      : payload?.results ?? payload?.items ?? []

    return {
      items: Array.isArray(items) ? items : [],
      count: Number(payload?.count ?? items.length),
      offset: safeOffset,
    }
  }, [])

  const loadHistory = useCallback(async (offset = 0) => {
    try {
      setHistoryLoading(true)
      setHistoryError('')
      const result = await fetchHistoryPage(offset)
      setHistory(result.items)
      setHistoryCount(result.count)
      setHistoryOffset(result.offset)
    } catch (err) {
      console.error('Failed to load OCR history:', err)
      setHistoryError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to load OCR history.',
      )
    } finally {
      setHistoryLoading(false)
    }
  }, [fetchHistoryPage])

  const loadRecentHistory = useCallback(async (offset = 0) => {
    try {
      setRecentHistoryLoading(true)
      setRecentHistoryError('')
      const result = await fetchHistoryPage(offset, 'COMPLETED')
      setRecentHistory(result.items)
      setRecentHistoryCount(result.count)
      setRecentHistoryOffset(result.offset)
    } catch (err) {
      console.error('Failed to load completed OCR history:', err)
      setRecentHistoryError(
        err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.message ||
          'Failed to load completed OCR history.',
      )
    } finally {
      setRecentHistoryLoading(false)
    }
  }, [fetchHistoryPage])

  const refreshOcrHistory = useCallback(async () => {
  await Promise.all([
    loadHistory(historyOffset),
    loadRecentHistory(recentHistoryOffset),
  ])
}, [
  loadHistory,
  loadRecentHistory,
  historyOffset,
  recentHistoryOffset,
])



  useEffect(() => {
    loadHistory(0)
    loadRecentHistory(0)
  }, [loadHistory, loadRecentHistory])

  useEffect(() => {
    let cancelled = false
    netsuiteApi.getMyConnection()
      .then((payload) => {
        const connectionData = payload?.data ?? payload ?? null
        if (!cancelled) setConnection(connectionData)
      })
      .catch((err) => {
        console.warn('No NetSuite connection available:', err)
        if (!cancelled) setConnection(null)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    return () => {
      selectedFiles.forEach(({ file }) => {
        if (file) {
          try {
            URL.revokeObjectURL(file.previewUrl)
          } catch {
            // Ignore cleanup errors.
          }
        }
      })
    }
  }, [selectedFiles])

  const validateFiles = useCallback((files) => {
    const incoming = Array.from(files || [])

    if (!incoming.length) {
      return { files: [], error: 'Please select at least one document file.' }
    }

    if (incoming.length > MAX_FILES) {
      return {
        files: [],
        error: `You can upload a maximum of ${MAX_FILES} files at once.`,
      }
    }

    const validated = []

    for (const file of incoming) {
      if (!ALLOWED_TYPES.includes(file.type)) {
        return {
          files: [],
          error: `${file.name}: unsupported file type.`,
        }
      }

      if (file.size <= 0) {
        return {
          files: [],
          error: `${file.name}: file is empty.`,
        }
      }

      if (file.size > MAX_FILE_SIZE) {
        return {
          files: [],
          error: `${file.name}: file size exceeds 10 MB.`,
        }
      }

      const category = getFileCategory(file)
      const categoryLimits = {
        PDF: 20 * 1024 * 1024,
        DOCX: 20 * 1024 * 1024,
        Image: 20 * 1024 * 1024,
        Spreadsheet: 10 * 1024 * 1024,
        CSV: 10 * 1024 * 1024,
        Text: 5 * 1024 * 1024,
      }

      const limit = categoryLimits[category] || MAX_FILE_SIZE
      if (file.size > limit) {
        return {
          files: [],
          error: `${file.name}: ${category} file size exceeds ${Math.round(limit / 1024 / 1024)} MB.`,
        }
      }

      validated.push({
        id: `${file.name}-${file.lastModified}-${Math.random()}`,
        file,
        previewUrl: createPreview(file),
      })
    }

    return { files: validated, error: '' }
  }, [])

  const addFiles = useCallback(
    (fileList) => {
      const incoming = Array.from(fileList || [])
      if (!incoming.length) return

      const remainingSlots = MAX_FILES - selectedFiles.length

      if (remainingSlots <= 0) {
        setError(`You can upload a maximum of ${MAX_FILES} files at once.`)
        return
      }

      const limitedIncoming = incoming.slice(0, remainingSlots)
      const { files, error: validationError } = validateFiles(limitedIncoming)

      if (validationError) {
        setError(validationError)
        return
      }

      setError('')
      setSelectedFiles((current) => {
        const existingKeys = new Set(
          current.map(
            ({ file }) => `${file.name}-${file.size}-${file.lastModified}`,
          ),
        )

        const merged = [...current]

        for (const item of files) {
          const key = `${item.file.name}-${item.file.size}-${item.file.lastModified}`

          if (!existingKeys.has(key)) {
            merged.push(item)
            existingKeys.add(key)
          } else {
            URL.revokeObjectURL(item.previewUrl)
          }
        }

        return merged
      })

      setResults([])
      setActiveIndex(0)
    },
    [selectedFiles.length, validateFiles],
  )

  const handleFileChange = (event) => {
    addFiles(event.target.files)
    event.target.value = ''
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragActive(false)
    addFiles(event.dataTransfer.files)
  }

  const removeSelectedFile = (index) => {
    setSelectedFiles((current) => {
      const target = current[index]

      if (target?.previewUrl) {
        URL.revokeObjectURL(target.previewUrl)
      }

      return current.filter((_, itemIndex) => itemIndex !== index)
    })

    setResults([])
    setActiveIndex(0)
    setError('')
  }

  const clearSelection = () => {
    selectedFiles.forEach(({ previewUrl }) => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    })

    setSelectedFiles([])
    setResults([])
    setActiveIndex(0)
    setError('')
  }

  const handleExtract = async () => {
      if (!selectedFiles.length || processing) {
        if (!selectedFiles.length) {
          setError('Please select at least one document file first.')
        }
        return
      }

    try {
      setError('')
      setProcessing(true)
      setResults([])
      setActiveIndex(0)

      const formData = new FormData()

      selectedFiles.forEach(({ file }) => {
        formData.append('files', file)
      })

      if (extractionConfig?.template_id) {
        formData.append('template_id', extractionConfig.template_id)
      } else if (extractionConfig?.requested_fields) {
        formData.append(
          'requested_fields',
          JSON.stringify(extractionConfig.requested_fields),
        )
      }

      const response = await apiClient.post(
        '/ocr/test-extract/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        },
      )

      const payload = response?.data ?? {}
      const batchId = payload?.batch_id

      if (!batchId) {
        throw new Error('OCR batch was created without a batch ID.')
      }

      const initialFiles = Array.isArray(payload.files)
        ? payload.files.map((item) => ({
            status: item.status || 'UPLOADED',
            upload_id: item.upload_id || null,
            filename: item.filename || null,
            data: null,
            error: null,
          }))
        : []

      setResults(initialFiles)

      const terminalStatuses = new Set([
        'COMPLETED',
        'PARTIAL',
        'FAILED',
      ])

      const startedAt = Date.now()
      const maxPollingMs = 30 * 60 * 1000

      while (Date.now() - startedAt < maxPollingMs) {
        const statusResponse = await apiClient.get(
          `/ocr/test-extract/batches/${batchId}/`,
        )

        const batch = statusResponse?.data ?? {}
        const files = Array.isArray(batch?.files)
          ? batch.files
          : []

        setResults(files)
        sessionStorage.setItem(
          `ocr_test_live_results_${batchId}`,
          JSON.stringify(files),
          )
        setActiveIndex((current) => {
          if (!files.length) return 0
          return Math.min(current, files.length - 1)
        })

        const completedOrFailed = files.some((item) => 
          ['COMPLETED', 'FAILED'].includes(
              item.status,
            ),
          )

        if (completedOrFailed) {
          sessionStorage.setItem(
        `ocr_test_result`,
        JSON.stringify({
          status: batch?.status ?? 'PROCESSING',
          batch_id: batchId,
          files,
          requested_fields: extractionConfig?.requested_fields || null,
        }),
          )
        }

        const allTerminal =
          files.length > 0 &&
          files.every((item) =>
            ['COMPLETED', 'FAILED'].includes(item.status),
          )

        if (
          allTerminal ||
          terminalStatuses.has(batch?.status)
        ) {
          break
        }

        await new Promise((resolve) => setTimeout(resolve, 1500))
      }

      clearSelectedFilesAfterExtraction()
      await refreshOcrHistory()
    } catch (err) {
      console.error('OCR batch submission failed:', err)

      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'OCR batch processing failed.'

      setError(detail)
    } finally {
      setProcessing(false)
    }
  }

  const activeResult = results[activeIndex] ?? null
  const openFieldMapping = () => {
    if (!activeResult) {
      setError('Extract a file before opening Field Mapping.')
      return
    }

    sessionStorage.setItem(
      'ocr_field_mapping_context',
      JSON.stringify({
        connection_id: connection?.id || null,
        record_type: 'vendorBill',
        upload_id: activeResult.upload_id || null,
        document_id: activeResult.document_id || null,
        filename: activeResult.filename || null,
        data: activeResult.data || {},
        requested_fields:
          extractionConfig?.requested_fields || null,
      }),
    )

    navigate('/app/ocr-test/field-mapping')
  }


  const activeSelectedItem = selectedFiles.find(({ file }) => {
    if (!activeResult?.filename) return false

    return (
      file?.name === activeResult.filename ||
      file?.name?.toLowerCase() === activeResult.filename?.toLowerCase()
    )
  })

  const activeFile =
    results.length > 0
      ? activeSelectedItem?.file ?? null
      : selectedFiles[activeIndex]?.file ?? null

  const activePreviewUrl =
    remotePreviewUrl ??
    activeSelectedItem?.previewUrl ??
    selectedFiles[activeIndex]?.previewUrl ??
    (activeResult?.upload_id
      ? `/ocr/test-extract/uploads/${activeResult.upload_id}/preview/`
      : null)

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    const previewEndpoint =
      activeResult?.preview_url ||
      (activeResult?.upload_id
        ? `/ocr/test-extract/uploads/${activeResult.upload_id}/preview/`
        : null)

    const loadRemotePreview = async () => {
      setPreviewError('')
      setRemotePreviewUrl(null)

      if (!previewEndpoint) {
        return
      }

      try {
        const response = await apiClient.get(
          previewEndpoint,
          { responseType: 'blob' },
        )

        if (cancelled) {
          return
        }

        objectUrl = URL.createObjectURL(response.data)
        setRemotePreviewUrl(objectUrl)
      } catch (err) {
        console.error('Failed to load OCR file preview:', err)

        if (!cancelled) {
          setPreviewError(
            err?.response?.data?.detail ||
              err?.message ||
              'Unable to load file preview.',
          )
        }
      }
    }

    loadRemotePreview()

    return () => {
      cancelled = true

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [activeResult?.preview_url, activeResult?.upload_id])

  const canSlide = results.length > 1

  const goPrevious = () => {
    if (!results.length) return

    setActiveIndex((current) =>
      current <= 0 ? results.length - 1 : current - 1,
    )
  }

  const goNext = () => {
    if (!results.length) return

    setActiveIndex((current) =>
      current >= results.length - 1 ? 0 : current + 1,
    )
  }

  const formatDate = (value) => {
    if (!value) return '--'

    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '--'

    return date.toLocaleString()
  }

  const statusLabel = (status) => {
    if (!status) return 'Unknown'
    return String(status).replaceAll('_', ' ')
  }

  const statusClass = (status) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-emerald-600'
      case 'FAILED':
        return 'text-red-600'
      case 'PROCESSING':
        return 'text-amber-600'
      default:
        return 'text-[var(--color-muted)]'
    }
  }

  return (
    <ClientLayout title="OCR" breadcrumb="OCR">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        {/* Upload / actions */}
        <Card className="p-5 sm:p-6">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
                OCR
              </h1>

              <p className="text-sm text-[var(--color-muted)]">
                Upload PDF, image, spreadsheet, or text files and extract structured
                document data.
              </p>
            </div>

            <div
              onDragEnter={(event) => {
                event.preventDefault()
                setDragActive(true)
              }}
              onDragOver={(event) => {
                event.preventDefault()
                setDragActive(true)
              }}
              onDragLeave={(event) => {
                event.preventDefault()
                setDragActive(false)
              }}
              onDrop={handleDrop}
              className={`rounded-2xl border-2 border-dashed p-5 transition sm:p-7 ${
                dragActive
                  ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                  : 'border-[var(--color-border)] bg-[var(--color-surface)]'
              }`}
            >
              <div className="flex flex-col items-center justify-center text-center">
                <div className="mb-3 rounded-full bg-[var(--color-canvas)] px-4 py-2 text-sm font-medium text-[var(--color-ink)]">
                  Drag & drop files here
                </div>

                <p className="text-sm text-[var(--color-muted)]">
                  PDF, image, spreadsheet, or text files · up to {MAX_FILES} inputs · max
                  20 MB per direct file
                </p>

                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  onChange={handleFileChange}
                  disabled={processing}
                  className="hidden"
                />

                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <Button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    disabled={processing}
                  >
                    Choose Files
                  </Button>

                  <Button
                    type="button"
                    intent="secondary"
                    onClick={clearSelection}
                    disabled={processing || !selectedFiles.length}
                  >
                    Clear
                  </Button>

                  <Button
                    type="button"
                    onClick={handleExtract}
                    disabled={processing || !selectedFiles.length}
                  >
                    {processing ? 'Processing...' : 'Extract Data'}
                  </Button>
                </div>
              </div>

              </div>

              {selectedFiles.length > 0 && (
                <ExtractionConfigPanel onChange={setExtractionConfig} />
              )}

              {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {!!selectedFiles.length && (
              <div>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--color-ink)]">
                      Selected files ({selectedFiles.length})
                    </p>

                    <p className="text-xs text-[var(--color-muted)]">
                      Files will be processed independently in one OCR batch.
                    </p>
                  </div>
                </div>

                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {selectedFiles.map((item, index) => (
                    <div
                      key={item.id}
                      className={`flex items-center gap-3 rounded-xl border p-3 ${
                        index === activeIndex
                          ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                          : 'border-[var(--color-border)]'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setActiveIndex(index)}
                        className="min-w-0 flex-1 text-left"
                        disabled={processing}
                      >
                        <p className="truncate text-sm font-medium text-[var(--color-ink)]">
                          {item.file.name}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-muted)]">
                          {(item.file.size / 1024 / 1024).toFixed(2)} MB
                          {!isImage(item.file) && !isPdf(item.file) ? ` · ${getFileCategory(item.file)}` : ''}
                        </p>
                      </button>

                      <button
                        type="button"
                        onClick={() => removeSelectedFile(index)}
                        disabled={processing}
                        className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                        aria-label={`Remove ${item.file.name}`}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Result workspace */}
        {(selectedFiles.length > 0 || results.length > 0) && (
          <div className="grid min-h-[560px] gap-6 lg:grid-cols-2">
            {/* Left: preview */}
            <Card className="flex min-h-[520px] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    File Preview
                  </p>

                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {activeResult?.filename ||
                      activeFile?.name ||
                      'Select a file'}
                  </p>
                </div>

                <div className="shrink-0 text-xs font-medium text-[var(--color-muted)]">
                  {results.length
                    ? `${activeIndex + 1} / ${results.length}`
                    : selectedFiles.length
                      ? `${activeIndex + 1} / ${selectedFiles.length}`
                      : '0 / 0'}
                </div>
              </div>

              <div className="flex min-h-0 flex-1 items-center justify-center bg-[var(--color-canvas)] p-4">
                {previewError && (
                  <div className="max-w-md rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
                    {previewError}
                  </div>
                )}

                {!previewError &&
                  activeFile &&
                  (isPdf(activeFile) || isImage(activeFile)) &&
                  activePreviewUrl && (
                    isPdf(activeFile) ? (
                      <div className="flex h-full w-full flex-col gap-3">
                        <iframe
                          title={activeFile.name}
                          src={activePreviewUrl}
                          className="min-h-[420px] w-full rounded-lg border border-[var(--color-border)] bg-white"
                        />
                        <a
                          href={activePreviewUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-center text-sm font-medium text-[var(--color-primary)] hover:underline"
                        >
                          Open PDF in new tab
                        </a>
                      </div>
                    ) : (
                      <img
                        src={activePreviewUrl}
                        alt={activeFile.name}
                        className="max-h-[430px] max-w-full rounded-lg object-contain shadow-sm"
                      />
                    )
                  )}

                {!previewError &&
                  activeFile &&
                  !isPdf(activeFile) &&
                  !isImage(activeFile) && (
                    <div className="max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center">
                      <p className="text-sm font-semibold text-[var(--color-ink)]">
                        {activeFile.name}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {getFileCategory(activeFile)} file
                      </p>
                      <p className="mt-2 text-sm text-[var(--color-muted)]">
                        Preview is not available for this format. The file will be
                        processed server-side and extraction results will appear here.
                      </p>
                    </div>
                  )}

                {!previewError &&
                  !activeFile &&
                  !activeResult?.preview_url &&
                  !activeResult?.upload_id && (
                    <p className="text-sm text-[var(--color-muted)]">
                      Select a file to preview it.
                    </p>
                  )}

              </div>

              <div className="flex items-center justify-between border-t border-[var(--color-border)] p-4">
                <Button
                  type="button"
                  intent="secondary"
                  onClick={goPrevious}
                  disabled={!canSlide}
                >
                  ← Previous
                </Button>

                <span className="text-xs text-[var(--color-muted)]">
                  {canSlide ? 'Switch file' : 'Single file'}
                </span>

                <Button
                  type="button"
                  intent="secondary"
                  onClick={goNext}
                  disabled={!canSlide}
                >
                  Next →
                </Button>
              </div>
            </Card>

            {/* Right: review workspace */}
            <Card className="flex min-h-[520px] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    OCR Review
                  </p>

                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {activeResult?.filename || activeFile?.name || 'Waiting for extraction'}
                  </p>
                </div>

                {activeResult && (
                  <Button
                    type="button"
                    intent="secondary"
                    size="sm"
                    onClick={openFieldMapping}
                    disabled={!connection?.id}
                  >
                    Map Fields with NetSuite
                  </Button>
                )}

                {activeResult?.status && (
                  <span
                    className={`shrink-0 text-xs font-semibold uppercase tracking-wide ${statusClass(activeResult.status)}`}
                  >
                    {statusLabel(activeResult.status)}
                  </span>
                )}
              </div>

              <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-surface)] p-4">
                {activeResult ? (
                  <OcrReviewWorkspace
                    result={activeResult}
                    onSaved={(savedResult) => {
                      setResults((current) =>
                        current.map((item, index) =>
                          index === activeIndex
                            ? { ...item, ...savedResult }
                            : item,
                        ),
                      )
                      refreshOcrHistory()
                    }}
                    customFieldTypes={
                      extractionConfig?.requested_fields?.custom_fields?.reduce(
                        (acc, cf) => {
                          if (cf.label && cf.key) {
                            acc[cf.key] = cf.data_type || 'text'
                          }
                          return acc
                        },
                        {},
                      ) || {}
                    }
                    connectionId={connection?.id || null}
                    requestedFields={extractionConfig?.requested_fields || null}
                    validationResult={validationResult}
                    onValidate={async (documentId) => {
                      const result = await netsuiteApi.validateDocument(documentId)
                      setValidationResult(result)
                      refreshOcrHistory()
                    }}
                    onPost={async (documentId, connId) => {
                      await netsuiteApi.postVendorBill(documentId, connId || connection?.id)
                      await refreshOcrHistory()
                    }}
                  />
                ) : (
                  <div className="flex min-h-[400px] items-center justify-center text-center">
                    <div>
                      <p className="text-sm font-medium text-[var(--color-ink)]">
                        Upload files and click Extract Data
                      </p>
                      <p className="mt-1 text-sm text-[var(--color-muted)]">
                        The result for the active file will appear here.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between border-t border-[var(--color-border)] p-4">
                <Button
                  type="button"
                  intent="secondary"
                  onClick={goPrevious}
                  disabled={!canSlide}
                >
                  ← Previous
                </Button>

                <span className="text-xs text-[var(--color-muted)]">
                  {results.length
                    ? `${activeIndex + 1} / ${results.length} result`
                    : 'No result yet'}
                </span>

                <Button
                  type="button"
                  intent="secondary"
                  onClick={goNext}
                  disabled={!canSlide}
                >
                  Next →
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* OCR Validation & Posting */}
        <Card className="p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                OCR Validation & Posting
              </h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Review completed OCR files, validate them against NetSuite, and post validated Vendor Bills in bulk.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={validationFilter}
                onChange={(e) => {
                  setValidationFilter(e.target.value)
                  setSelectedIds(new Set())
                }}
                className="rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
              >
                <option value="all">All Data</option>
                <option value="correct">Correct Data</option>
                <option value="incorrect">Incorrect Data</option>
              </select>

              <Button
                type="button"
                intent="secondary"
                size="sm"
                onClick={toggleSelectAll}
                disabled={!selectableHistory.length}
              >
                {allVisibleSelected ? 'Deselect All' : 'Select All'}
              </Button>

              {selectedValidateIds.length > 0 && (
                <Button
                  type="button"
                  intent="secondary"
                  size="sm"
                  onClick={() => handleBatchValidate(selectedValidateIds)}
                  disabled={processing}
                >
                  {selectedHistoryItems.some(
                    (item) => item.validation_status === 'VALIDATION_FAILED',
                  )
                    ? `Validate Again (${selectedValidateIds.length})`
                    : `Validate (${selectedValidateIds.length})`}
                </Button>
              )}

              {selectedHistoryItems.some((item) => item?.status === 'COMPLETED' && !item?.document_id) && (
                <span className="text-xs text-amber-700">Save selected OCR results before posting.</span>
              )}

              {selectedCompletedItems.length > 0 && (
                <Button
                  type="button"
                  intent="primary"
                  size="sm"
                  onClick={handlePostSelected}
                  disabled={processing}
                >
                  {`Post (${selectedCompletedItems.length})`}
                </Button>
              )}

              <Button
                type="button"
                intent="secondary"
                size="sm"
                onClick={() => refreshOcrHistory()}
                disabled={historyLoading || recentHistoryLoading}
              >
                {historyLoading || recentHistoryLoading ? 'Refreshing...' : 'Refresh'}
              </Button>
            </div>
          </div>

          {historyError && (
            <p className="mb-4 text-sm text-red-600">{historyError}</p>
          )}

          {historyLoading ? (
            <div className="rounded-lg border border-[var(--color-border)] p-5 text-sm text-[var(--color-muted)]">
              Loading OCR processing history...
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">No OCR files yet</p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Uploaded files will appear here while they move through processing and validation.
              </p>
            </div>
          ) : (
            <>
              <div className="max-h-[430px] overflow-auto rounded-lg border border-[var(--color-border)]">
                <div className="divide-y divide-[var(--color-border)]">
                  {filteredHistory.map((item) => {
                    const itemId = item?.document_id || item?.upload_id
                    const isSelected = selectedIds.has(itemId)
                    const isCompleted = item?.status === 'COMPLETED'
                    const isSelectable = isCompleted && Boolean(itemId)

                    return (
                      <div
                        key={item.upload_id || item.document_id}
                        className={`flex items-center gap-4 p-4 transition ${
                          isSelected
                            ? 'bg-[var(--color-primary-soft)]'
                            : 'hover:bg-[var(--color-canvas)]'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={!isSelectable}
                          onChange={() => isSelectable && toggleSelect(itemId)}
                          className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
                          title={
                            isSelectable
                              ? 'Select this completed OCR file'
                              : 'Only completed OCR files can be selected'
                          }
                        />

                        <div className="min-w-0 flex-1">
                          <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                            {item.filename || 'Unnamed file'}
                          </p>
                          <p className="mt-1 text-xs text-[var(--color-muted)]">
                            {formatDate(item.created_at)}
                          </p>
                        </div>

                        <div className="shrink-0 text-right">
                          <p className={`text-xs font-semibold uppercase tracking-wide ${statusClass(item.status)}`}>
                            {statusLabel(item.status)}
                          </p>
                          {item.validation_status && (
                            <p className={`mt-1 text-xs font-semibold ${item.validation_status === 'VALIDATED' ? 'text-emerald-600' : 'text-red-600'}`}>
                              {item.validation_status === 'VALIDATED' ? '✓ Validated' : '✕ Failed'}
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {historyCount > HISTORY_PAGE_SIZE && (
                <div className="mt-4 flex items-center justify-between gap-3">
                  <Button
                    type="button"
                    intent="secondary"
                    onClick={() => loadHistory(Math.max(0, historyOffset - HISTORY_PAGE_SIZE))}
                    disabled={historyLoading || historyOffset === 0}
                  >
                    ← Previous
                  </Button>
                  <span className="text-xs text-[var(--color-muted)]">
                    Page {Math.floor(historyOffset / HISTORY_PAGE_SIZE) + 1} of{' '}
                    {Math.max(1, Math.ceil(historyCount / HISTORY_PAGE_SIZE))}
                  </span>
                  <Button
                    type="button"
                    intent="secondary"
                    onClick={() => loadHistory(historyOffset + HISTORY_PAGE_SIZE)}
                    disabled={historyLoading || historyOffset + HISTORY_PAGE_SIZE >= historyCount}
                  >
                    Next →
                  </Button>
                </div>
              )}
            </>
          )}
        </Card>

        {/* Recent OCR History */}
        <Card className="p-5 sm:p-6">
          <div className="mb-5">
            <h2 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              Recent OCR History
            </h2>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Successfully extracted files are kept here as the permanent OCR history.
            </p>
          </div>

          {recentHistoryError && (
            <p className="mb-4 text-sm text-red-600">{recentHistoryError}</p>
          )}

          {recentHistoryLoading ? (
            <div className="rounded-lg border border-[var(--color-border)] p-5 text-sm text-[var(--color-muted)]">
              Loading completed OCR history...
            </div>
          ) : recentHistory.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--color-border)] p-8 text-center">
              <p className="text-sm font-medium text-[var(--color-ink)]">No completed OCR files yet</p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                A file will appear here as soon as extraction completes.
              </p>
            </div>
          ) : (
            <>
              <div className="divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)]">
                {recentHistory.map((item) => (
                  <div
                    key={item.upload_id || item.document_id}
                    className="flex items-center gap-4 p-4 transition hover:bg-[var(--color-canvas)]"
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => {
                        if (item.document_id) {
                          navigate(`/app/ocr-test/history/${item.document_id}`)
                        } else if (item.batch_id) {
                          navigate(`/app/ocr-test/history/batch/${item.batch_id}`)
                        }
                      }}
                    >
                      <p className="break-all text-sm font-medium text-[var(--color-ink)]">
                        {item.filename || 'Unnamed file'}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {formatDate(item.created_at)}
                      </p>
                    </button>

                    <span className={`shrink-0 text-xs font-semibold uppercase tracking-wide ${statusClass(item.status)}`}>
                      {statusLabel(item.status)}
                    </span>

                    <Button
                      type="button"
                      intent="secondary"
                      size="sm"
                      disabled={!item.document_id && !item.batch_id}
                      onClick={() => {
                        if (item.document_id) {
                          navigate(`/app/ocr-test/history/${item.document_id}`)
                        } else if (item.batch_id) {
                          navigate(`/app/ocr-test/history/batch/${item.batch_id}`)
                        }
                      }}
                    >
                      View Result
                    </Button>
                  </div>
                ))}
              </div>

              {recentHistoryCount > HISTORY_PAGE_SIZE && (
                <div className="mt-4 flex items-center justify-between gap-3">
                  <Button
                    type="button"
                    intent="secondary"
                    onClick={() => loadRecentHistory(Math.max(0, recentHistoryOffset - HISTORY_PAGE_SIZE))}
                    disabled={recentHistoryLoading || recentHistoryOffset === 0}
                  >
                    ← Previous
                  </Button>
                  <span className="text-xs text-[var(--color-muted)]">
                    Page {Math.floor(recentHistoryOffset / HISTORY_PAGE_SIZE) + 1} of{' '}
                    {Math.max(1, Math.ceil(recentHistoryCount / HISTORY_PAGE_SIZE))}
                  </span>
                  <Button
                    type="button"
                    intent="secondary"
                    onClick={() => loadRecentHistory(recentHistoryOffset + HISTORY_PAGE_SIZE)}
                    disabled={recentHistoryLoading || recentHistoryOffset + HISTORY_PAGE_SIZE >= recentHistoryCount}
                  >
                    Next →
                  </Button>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
      </ClientLayout>
    )
  }