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
  
  switchConnection: (id) => apiClient.post(`${NETSUITE_ENDPOINTS.connections}${id}/switch/`).then(unwrap),

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

  testConnection: (connectionId) =>
    apiClient.post(
      `${NETSUITE_ENDPOINTS.companyConnections}${connectionId}/test/`,
    ).then((response) => response.data),
  
  getCustomers: (params) => apiClient.get(NETSUITE_ENDPOINTS.customers, { params }).then(unwrap),
  
  getCustomer: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.customers}${id}/`).then(unwrap),
  
  getEmployees: (params) => apiClient.get(NETSUITE_ENDPOINTS.employees, { params }).then(unwrap),
  
  getEmployee: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.employees}${id}/`).then(unwrap),
  
  getVendors: (params) => apiClient.get(NETSUITE_ENDPOINTS.vendors, { params }).then(unwrap),
  
  getVendor: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.vendors}${id}/`).then(unwrap),
  
  getItems: (type = 'inventoryItem', params) => apiClient.get(NETSUITE_ENDPOINTS.items, { params: { type, ...params } }).then(unwrap),
  
  getItem: (id, type = 'inventoryItem') => apiClient.get(`${NETSUITE_ENDPOINTS.items}${id}/`, { params: { type } }).then(unwrap),
  
  getSalesOrders: (params) => apiClient.get(NETSUITE_ENDPOINTS.salesOrders, { params }).then(unwrap),
  
  getSalesOrder: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.salesOrders}${id}/`).then(unwrap),
  
  getPurchaseOrders: (params) => apiClient.get(NETSUITE_ENDPOINTS.purchaseOrders, { params }).then(unwrap),
  
  getPurchaseOrder: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.purchaseOrders}${id}/`).then(unwrap),
  
  getInvoices: (params) => apiClient.get(NETSUITE_ENDPOINTS.invoices, { params }).then(unwrap),
  
  getInvoice: (id) => apiClient.get(`${NETSUITE_ENDPOINTS.invoices}${id}/`).then(unwrap),
  
  // Phase 3: OCR Field Mapping
  getFieldCatalogue: (connectionId, recordType = 'vendorBill', forceRefresh = false,) =>
    apiClient.get('/netsuite/ocr/field-catalogue/', { params: { connection_id: connectionId, record_type: recordType, ...(forceRefresh ? {force_refresh: 'true'} : {}) } }).then(unwrap),

  suggestFieldMappings: (connectionId, recordType='vendorBill', sourceFields =[]) =>
    apiClient.post('/netsuite/ocr/suggest-mapping/', { connection_id: connectionId, record_type: recordType, source_fields: sourceFields }).then(unwrap),
  
  listFieldMappings: (connectionId, recordType = 'vendorBill') =>
    apiClient.get('/netsuite/ocr/field-mappings/', { params: { connection_id: connectionId, record_type: recordType } }).then(unwrap),
  
  saveFieldMappings: (connectionId, recordType, mappings = []) =>
    apiClient.post('/netsuite/ocr/field-mappings/', { connection_id: connectionId, record_type: recordType, mappings }).then(unwrap),
  
  validateDocument: (documentId, connectionId) => 
    apiClient.post('/netsuite/ocr/validate/',{document_id:documentId,connection_id: connectionId}).then(unwrap),

  checkOCRReferences: (documentId, connectionId) =>
    apiClient.post(
    '/netsuite/ocr/check-references/',
    {
      document_id: documentId,
      connection_id: connectionId,
    },
  ).then(unwrap),
  
  postOCRVendorBill: (documentId, connectionId) => 
    apiClient.post('/netsuite/ocr/post-vendor-bill/',{document_id:documentId, connection_id:connectionId}).then(unwrap),

  createCustomField: (payload) =>
    apiClient
      .post('/netsuite/ocr/custom-fields/', payload)
      .then(unwrap),

  }

