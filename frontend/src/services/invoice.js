import apiClient, { unwrap } from './apiClient.js'

export const invoiceApi = {
  upload: (files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return apiClient.post('/invoice/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(unwrap)
  },
  listBatches: (params) => apiClient.get('/api/v1/invoice/batches/', { params }).then(unwrap),
  getBatch: (id) => apiClient.get(`/api/v1/invoice/batches/${id}/`).then(unwrap),
  getFile: (id) => apiClient.get(`/api/v1/invoice/files/${id}/`).then(unwrap),
  deleteFile: (id) => apiClient.delete(`/api/v1/invoice/files/${id}/`).then(unwrap),
  retryFile: (id) => apiClient.post(`/api/v1/invoice/files/${id}/retry/`).then(unwrap),
  patchExtraction: (id, data) => apiClient.patch(`/api/v1/invoice/files/${id}/extraction/`, { extracted_json: data }).then(unwrap),
  reviewFile: (id, payload) => apiClient.post(`/api/v1/invoice/review/${id}/`, payload).then(unwrap),
  getFileHistory: (id) => apiClient.get(`/api/v1/invoice/files/${id}/`).then(unwrap).then((data) => data?.extraction?.review_history || []),
  previewPayload: (id) => apiClient.post(`/api/v1/invoice/preview-payload/${id}/`).then(unwrap),
}