import apiClient, { unwrap } from './apiClient.js'

const normalizeList = (payload) => {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  return []
}

export const ocrApi = {
  listExtractionTemplates: () =>
    apiClient.get('/ocr/extraction-templates/').then(unwrap).then(normalizeList),
}
