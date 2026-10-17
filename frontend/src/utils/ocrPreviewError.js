export async function getPreviewErrorMessage(error) {
  const responseData = error?.response?.data
  let payload = responseData

  if (typeof Blob !== 'undefined' && responseData instanceof Blob) {
    try {
      const text = await responseData.text()
      payload = text ? JSON.parse(text) : null
    } catch {
      payload = null
    }
  } else if (typeof responseData === 'string') {
    try {
      payload = JSON.parse(responseData)
    } catch {
      payload = null
    }
  }

  const detail = payload?.detail || payload?.error || payload?.message
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }

  if (error?.response?.status === 404) {
    return 'The original uploaded file is no longer available, so its preview cannot be displayed. Your saved OCR result is still available. Re-upload the source file if you need to view it again.'
  }

  return 'Unable to load the original file preview right now. Your saved OCR result is still available. Please try again, or re-upload the source file if the preview remains unavailable.'
}