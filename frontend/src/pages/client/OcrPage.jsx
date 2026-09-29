import { useCallback, useState, useRef, useMemo, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import apiClient, { unwrap } from '../../services/apiClient.js'
import { netsuiteApi } from '../../services/netsuite.js'
import { useToast } from '../../components/ui/Toast.jsx'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import OcrReviewWorkspace from '../../components/ocr/OcrReviewWorkspace.jsx'


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
const MAX_FILES = 200

function createPreview(file) {
  if (!file) return null
  return URL.createObjectURL(file)
}

function isImage(file) {
  return file?.type?.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp|tiff)$/i.test(file?.name || '')
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


export default function OcrPage() {

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
  const location = useLocation()
  const inputRef = useRef(null)
  const { addToast } = useToast()

  const [selectedFiles, setSelectedFiles] = useState([])
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [results, setResults] = useState([])
  const [draftResults, setDraftResults] = useState({})
  const [savingAll, setSavingAll] = useState(false)
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

  const [extractionTemplates, setExtractionTemplates] = useState([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')

  const [validationFilter, setValidationFilter] = useState('all')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [connection, setConnection] = useState(null)
  const [validationResult, setValidationResult] = useState(null)
  const [ocrMode, setOcrMode] = useState('')
  const [ocrModes, setOcrModes] = useState({
    single: true,
    multiple: false,
  })
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
  () =>
    filteredHistory.filter((item) => {
      const hasDocument = Boolean(item?.document_id)

      const canRetryValidation =
        item?.validation_status === 'VALIDATION_FAILED'

      const isCompleted =
        item?.status === 'COMPLETED'

      return (
        hasDocument &&
        (isCompleted || canRetryValidation)
      )
    }),
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
          item?.document_id &&
          (
            item?.validation_status === 'VALIDATION_FAILED' ||
            (
              item?.status === 'COMPLETED' &&
              !item?.validation_status
            )
          ),
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
          connection_id: connection?.id || null,
        },
      )

      const queued = unwrap(response) || {}
      const job = await waitForBatchJob(
        queued?.job_id || queued?.id,
      )

      const jobResults = Array.isArray(job?.results)
        ? job.results
        : Array.isArray(job?.result?.results)
          ? job.result.results
          : []

      const resultFailedCount = jobResults.filter(
        (item) =>
          ['FAILED', 'VALIDATION_FAILED'].includes(
            String(item?.status || '').toUpperCase(),
          ),
      ).length

      const failedCount = Math.max(
        Number(
          job?.failed ??
            job?.result?.failed ??
            0,
        ),
        resultFailedCount,
      )
      const completedCount = Number(
        job?.completed ??
          job?.succeeded ??
          job?.result?.completed ??
          job.result?.succeeded ??
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
          connection_id: connection?.id || null,
        },
      )

      const queued = unwrap(response) || {}
      const job = await waitForBatchJob(
        queued?.job_id || queued?.id,
      )

      const failedCount = Number(
        job?.failed ??
          job?.result?.failed ??
          0,
      )
      const completedCount = Number(
        job?.completed ??
          job?.succeeded ??
          job?.result?.completed ??
          job?.result?.succeeded ??
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
  let cancelled = false

  const stateJobId =
    location.state?.validationJobId

  const storedJob = (() => {
    try {
      const raw = sessionStorage.getItem(
        'ocr_netsuite_validation_job',
      )

      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })()

  const jobId =
    stateJobId ||
    storedJob?.job_id ||
    null

  if (!jobId) {
    return undefined
  }

  const monitor = async () => {
    try {
      const job = await waitForBatchJob(
        String(jobId),
      )

      if (cancelled) {
        return
      }

      const status = String(
        job?.status || '',
      ).toUpperCase()

      if (status === 'SUCCESS') {
        await refreshOcrHistory()
      } else {
        setError(
          job?.error ||
            'NetSuite validation batch did not complete successfully.',
        )
      }
    } catch (err) {
      if (!cancelled) {
        console.error(
          'NetSuite validation batch monitoring failed:',
          err,
        )

        setError(
          err?.response?.data?.detail ||
            err?.response?.data?.error ||
            err?.message ||
            'Unable to complete NetSuite validation.',
        )
      }
    } finally {
      if (!cancelled) {
        sessionStorage.removeItem(
          'ocr_netsuite_validation_job',
        )

        navigate(
          location.pathname,
          {
            replace: true,
            state: {},
          },
        )
      }
    }
  }

  monitor()

  return () => {
    cancelled = true
  }
}, [
  location,
  navigate,
  refreshOcrHistory,
  waitForBatchJob,
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
      selectedFiles.forEach(({ previewUrl }) => {
        if (previewUrl) {
          try {
            URL.revokeObjectURL(previewUrl)
          } catch {
            // Ignore cleanup errors.
          }
        }
      })
    }
  }, [selectedFiles])
  useEffect(() => {
    let cancelled = false

    const loadExtractionTemplates = async () => {
      try {
        const response = await apiClient.get('/ocr/extraction-templates/')
        const payload = response?.data?.data ?? response?.data ?? {}
        const templates = Array.isArray(payload) ? payload : []

        if (!cancelled) {
          setExtractionTemplates(templates)
        }
      } catch (err) {
        console.error('Failed to load OCR extraction templates:', err)
        if (!cancelled) {
          setExtractionTemplates([])
        }
      }
    }

    loadExtractionTemplates()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadOcrModes = async () => {
      try {
        const response = await apiClient.get('/ocr/extract/upload-modes/')
        const payload = response?.data ?? {}

        if (cancelled) return

        const singleEnabled = payload?.single?.enabled !== false
        const multipleEnabled = payload?.multiple?.enabled === true

        setOcrModes({
          single: singleEnabled,
          multiple: multipleEnabled,
        })

      } catch (err) {
        console.error('Failed to load OCR upload modes:', err)

        if (!cancelled) {
          setOcrModes({
            single: true,
            multiple: false,
          })
        }
      }
    }

    loadOcrModes()

    return () => {
      cancelled = true
    }
  }, [])

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

      if (!selectedTemplateId) {
        setError('Please select a File Template before uploading files.')
        return
      }

      if (!ocrMode) {
        setError('Please select an OCR mode before uploading files.')
        return
      }

      if (!incoming.length) return

      if (ocrMode === 'single') {
        if (incoming.length > 1) {
          setError('Single mode allows only one file at a time.')
          return
        }

        const { files, error: validationError } = validateFiles(incoming)

        if (validationError) {
          setError(validationError)
          return
        }

        selectedFiles.forEach(({ previewUrl }) => {
          if (previewUrl) {
            URL.revokeObjectURL(previewUrl)
          }
        })

        setError('')
        setSelectedFiles(files)
        setResults([])
        setActiveIndex(0)
        return
      }

      const remainingSlots = MAX_FILES - selectedFiles.length

      if (remainingSlots <= 0) {
        setError(
          `You can upload a maximum of ${MAX_FILES} files at once.`,
        )
        return
      }

      const limitedIncoming = incoming.slice(0, remainingSlots)
      const { files, error: validationError } =
        validateFiles(limitedIncoming)

      if (validationError) {
        setError(validationError)
        return
      }

      setError('')
      setSelectedFiles((current) => {
        const existingKeys = new Set(
          current.map(
            ({ file }) =>
              `${file.name}-${file.size}-${file.lastModified}`,
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
    [ocrMode, selectedFiles, selectedTemplateId, validateFiles],
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
    if (!selectedTemplateId) {
      setError('Please select a File Template before uploading or extracting files.')
      return
    }

    if (!ocrMode) {
      setError('Please select an OCR mode before extracting files.')
      return
    }

    if (!selectedFiles.length || processing) {
      if (!selectedFiles.length) {
        setError('Please select at least one document file first.')
      }
      return
    }

    if (ocrMode === 'single' && selectedFiles.length !== 1) {
      setError('Single mode allows exactly one file.')
      return
    }

    if (ocrMode === 'multiple' && !ocrModes.multiple) {
      setError('Multiple OCR is currently unavailable.')
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

      formData.append('mode', ocrMode)

      if (selectedTemplateId) {
          formData.append('template_id', selectedTemplateId)
      }

      const response = await apiClient.post(
        '/ocr/extract/',
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
            data: item.data || null,
            error: item.error || null,
            preview_url: item.preview_url || null,
          }))
        : []

      setResults(initialFiles)

      if (ocrMode === 'single') {
        sessionStorage.setItem(
          `ocr_test_live_results_${batchId}`,
          JSON.stringify(initialFiles),
        )

        sessionStorage.setItem(
          'ocr_test_result',
          JSON.stringify({
            status:
              payload?.status ??
              initialFiles[0]?.status ??
              'COMPLETED',
            batch_id: batchId,
            files: initialFiles,
            template_id: selectedTemplateId || null,
          }),
        )
        await refreshOcrHistory()
        return
      }

      const terminalStatuses = new Set([
        'COMPLETED',
        'PARTIAL',
        'FAILED',
      ])

      const startedAt = Date.now()
      const maxPollingMs = 30 * 60 * 1000

      while (Date.now() - startedAt < maxPollingMs) {
        const statusResponse = await apiClient.get(
          `/ocr/extract/batches/${batchId}/`,
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
          ['COMPLETED', 'FAILED'].includes(item.status),
        )

        if (completedOrFailed) {
          sessionStorage.setItem(
            'ocr_test_result',
            JSON.stringify({
              status: batch?.status ?? 'PROCESSING',
              batch_id: batchId,
              files,
              template_id: selectedTemplateId || null,
            }),
          )
        }

        const allTerminal =
          files.length > 0 &&
          files.every((item) =>
            ['COMPLETED', 'FAILED'].includes(item.status),
          )

        if (allTerminal || terminalStatuses.has(batch?.status)) {
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

  const activeSelectedItem = selectedFiles.find(({ file }) => {
    if (!activeResult?.filename) return false

    return (
      file?.name === activeResult.filename ||
      file?.name?.toLowerCase() === activeResult.filename?.toLowerCase()
    )
  })

  const activeFile =
    results.length > 0
      ? activeSelectedItem?.file ?? 
        (activeResult?.filename
          ? {
            name: activeResult.filename,
            type: 
              activeResult.mime_type ||
              activeResult.content_type ||
              '',
          }
          : null
        )
      : selectedFiles[activeIndex]?.file ?? null

  const activePreviewUrl =
    remotePreviewUrl ??
    activeSelectedItem?.previewUrl ??
    selectedFiles[activeIndex]?.previewUrl ??
    null

  useEffect(() => {
    let cancelled = false
    let objectUrl = null

    const loadRemotePreview = async () => {
      setPreviewError('')
      setRemotePreviewUrl(null)

      if (!activeResult?.preview_url) {
        return
      }

      try {
        const response = await apiClient.get(
          activeResult.preview_url,
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
  }, [activeResult?.preview_url])

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
        <Card className="p-4 sm:p-5">
          <div className="flex flex-col gap-3">
            <h1 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)] sm:text-2xl">
              OCR
            </h1>

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
              className={`flex flex-wrap items-center gap-3 rounded-xl border border-dashed p-3 transition ${
                dragActive
                  ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)]'
                  : 'border-transparent bg-[var(--color-canvas)]'
              }`}
            >
              <div className="flex min-w-[300px] flex-1 items-center gap-2 sm:max-w-xl">
                <label
                  htmlFor="ocr-extraction-template"
                  className="shrink-0 text-sm font-medium text-[var(--color-ink)]"
                >
                  File Template <span className="text-red-500">*</span>
                </label>
                <select
                  id="ocr-extraction-template"
                  value={selectedTemplateId}
                  onChange={(event) => setSelectedTemplateId(event.target.value)}
                  disabled={processing}
                  required
                  className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select File Template</option>
                  {extractionTemplates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="min-w-[150px]">
                <select
                  id="ocr-processing-mode"
                  value={ocrMode}
                  onChange={(event) => {
                    const nextMode = event.target.value
                    setOcrMode(nextMode)
                    setError('')
                    setResults([])
                    setActiveIndex(0)
                  }}
                  disabled={processing}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select Mode</option>
                  <option value="single" disabled={!ocrModes.single}>Single</option>
                  <option value="multiple" disabled={!ocrModes.multiple}>Multiple</option>
                </select>
              </div>

              <input
                ref={inputRef}
                type="file"
                multiple={ocrMode === 'multiple'}
                accept={ACCEPT}
                onChange={handleFileChange}
                disabled={processing || !selectedTemplateId || !ocrMode}
                className="hidden"
              />

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  disabled={processing || !selectedTemplateId || !ocrMode}
                >
                  Choose Files
                </Button>

                {!!selectedFiles.length && (
                  <>
                    <Button
                      type="button"
                      onClick={handleExtract}
                      disabled={processing || !selectedTemplateId || !ocrMode}
                    >
                      {processing ? 'Processing...' : 'Extract'}
                    </Button>
                    <Button
                      type="button"
                      intent="secondary"
                      onClick={clearSelection}
                      disabled={processing}
                    >
                      Clear
                    </Button>
                  </>
                )}
              </div>
              {dragActive && (
                <p className="w-full text-xs font-medium text-[var(--color-primary)]">
                  Drop files to add them
                </p>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {!!selectedFiles.length && (
              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-[var(--color-ink)]">
                    Selected files ({selectedFiles.length})
                  </p>
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
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left: preview */}
            <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
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

              <div className="min-h-0 flex-1 overflow-auto bg-[var(--color-canvas)] p-3">
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
                      <div className="flex min-h-full w-full flex-col gap-2">
                        <iframe
                          title={activeFile.name}
                          src={activePreviewUrl}
                          className="h-[340px] min-h-0 w-full rounded-lg border border-[var(--color-border)] bg-white"
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
                        className="max-h-[340px] max-w-full rounded-lg object-contain shadow-sm"
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
                  !activeResult?.preview_url && (
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
            <Card className="flex h-[480px] min-h-0 max-h-[70vh] flex-col overflow-hidden">
              <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] p-4">
                <div className="min-w-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                    OCR Review
                  </p>

                  <p className="mt-1 truncate text-sm font-semibold text-[var(--color-ink)]">
                    {activeResult?.filename || activeFile?.name || 'Waiting for extraction'}
                  </p>
                </div>

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
                    batchResults={results}
                    processingMode={ocrMode}
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
                      (extractionTemplates.find(
                        (template) =>
                          String(template?.id) === String(selectedTemplateId),
                      )?.fields_config?.custom_fields || []).reduce(
                        (acc, field) => {
                          const key = field?.key || field?.label
                          if (key) {
                            acc[key] = field?.data_type || 'text'
                          }
                          return acc
                        },
                        {},
                      )
                    }
                    connectionId={connection?.id || null}
                    validationResult={validationResult}
                    onValidate={async (documentId) => {
                      const connectionId = connection?.id
                      if(!documentId || !connectionId){
                        throw new Error(
                          'The OCR document or NetSuite connection is missing.',
                        )
                      }
                      const result = await netsuiteApi.validateDocument(documentId, connectionId)
                      setValidationResult(result)
                      refreshOcrHistory()
                    }}
                    onPost={async (documentId, connId) => {
                      const connectionId = connId || connection?.id
                      if (!documentId || !connectionId) {
                        throw new Error(
                          'The OCR document or NetSuite connection is missing.',
                        )
                      }
                      await netsuiteApi.postOCRVendorBill(documentId, connectionId)
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

      </div>
      </ClientLayout>
  )
}
  
