import apiClient, { unwrap } from './apiClient.js'
import { NETSUITE_ENDPOINTS } from '../utils/constants.js'

export const netsuiteApi = {
  // Connection management — a user can hold several NetSuite connections
  // (one per account), with exactly one marked active at a time.
  listConnections: () => apiClient.get(NETSUITE_ENDPOINTS.connections).then(unwrap),

  createConnection: (payload) => apiClient.post(NETSUITE_ENDPOINTS.companyConnections, payload).then(unwrap),
  
  renameConnection: (id, clientName) =>
    apiClient.patch(`${NETSUITE_ENDPOINTS.connections}${id}/`, { client_name: clientName }).then(unwrap),
  
  deleteConnection: (id) => apiClient.delete(`${NETSUITE_ENDPOINTS.connections}${id}/`).then(unwrap),
  
  getCompanyConnections: () => apiClient.get(NETSUITE_ENDPOINTS.companyConnections).then(unwrap),

  getMyConnections: () => apiClient.get(NETSUITE_ENDPOINTS.myConnections).then(unwrap),

  getMyConnection: () => apiClient.get(NETSUITE_ENDPOINTS.myConnection).then(unwrap),

  switchConnection: (id) =>
  apiClient
    .post(`${NETSUITE_ENDPOINTS.connections}${id}/switch/`)
    .then(unwrap),

  assignEmployee: (connectionId, employeeId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/assign-employee/`,
      { employee_id: employeeId },
    ).then(unwrap),

  removeEmployee: (connectionId, employeeId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/remove-employee/${employeeId}/`,
    ).then(unwrap),

    reconnectConnection: (connectionId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/reconnect/`,
    ).then(unwrap),

  reconnectConnection: (connectionId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/reconnect/`,
    ).then(unwrap),

  testConnection: (connectionId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/test/`,
    ).then((response) => response.data),
  
  
  
  getEmployees: (params) => apiClient.get(NETSUITE_ENDPOINTS.employees, { params }).then(unwrap),
  
  getEmployee: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.employees}${id}/`).then(unwrap),
  
  getInvoices: (params) => apiClient.get(NETSUITE_ENDPOINTS.invoices, { params }).then(unwrap),
  
  getInvoice: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.invoices}${id}/`).then(unwrap),
  
  validateDocument: (documentId, connectionId, config={}) => 
    apiClient.post('/netsuite/ocr/validate/',{document_id:documentId,connection_id: connectionId},config).then(unwrap),

  validateBatchDocuments: (documentIds, connectionId) =>
    apiClient.post('/netsuite/ocr/batch/validate/',{document_ids: documentIds, connection_id: connectionId,}).then(unwrap),

  getBatchJobStatus: (jobId) =>
  apiClient.get(`/netsuite/ocr/batch/jobs/${jobId}/`).then(unwrap),

  postOCRVendorBill: (documentId, connectionId, config={}) => 
    apiClient.post('/netsuite/ocr/post-vendor-bill/',{document_id:documentId, connection_id:connectionId},config).then(unwrap),
  batchPostDocuments: (documentIds, connectionId) =>
    apiClient.post('/netsuite/ocr/batch/post/', {
      document_ids: documentIds,
      connection_id: connectionId,
    }).then(unwrap)
}
