import { useCallback, useState } from 'react'
import { getApiErrorMessage } from '../utils/apiError.js'

export function useCrudResource() {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const clearFeedback = useCallback(() => {
    setError('')
    setMessage('')
  }, [])

  const loadResource = useCallback(async (action, fallback) => {
    setLoading(true)
    setError('')
    try {
      return await action()
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, fallback))
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const saveResource = useCallback(async (action, fallback) => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      await action()
      return true
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, fallback))
      return false
    } finally {
      setSaving(false)
    }
  }, [])

  const deleteResource = useCallback(async (action, fallback) => {
    setDeleting(true)
    setError('')
    setMessage('')
    try {
      await action()
      return true
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, fallback))
      return false
    } finally {
      setDeleting(false)
    }
  }, [])

  return {
    loading,
    saving,
    deleting,
    error,
    message,
    setError,
    setMessage,
    clearFeedback,
    loadResource,
    saveResource,
    deleteResource,
  }
}
