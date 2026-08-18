import apiClient, { unwrap } from './apiClient.js'
import { NETSUITE_ENDPOINTS } from '../utils/constants.js'

export const netsuiteApi = {
  // getConnectUrl: () => apiClient.get(NETSUITE_ENDPOINTS.connect).then(unwrap),
  // Connection management — a user can hold several NetSuite connections
  // (one per account), with exactly one marked active at a time.
  listConnections: () => apiClient.get(NETSUITE_ENDPOINTS.connections).then(unwrap),
  createConnection: (payload) => apiClient.post('/netsuite/company/connections/', payload).then(unwrap),
  renameConnection: (id, clientName) =>
    apiClient.patch(`${NETSUITE_ENDPOINTS.connections}${id}/`, { client_name: clientName }).then(unwrap),
  deleteConnection: (id) => apiClient.delete(`${NETSUITE_ENDPOINTS.connections}${id}/`).then(unwrap),
  switchConnection: (id) => apiClient.post(`${NETSUITE_ENDPOINTS.connections}${id}/switch/`).then(unwrap),
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
  // Company-level connection management
  getCompanyConnections: () => apiClient.get('/netsuite/company/connections/').then(unwrap),
  assignEmployee: (connectionId, employeeId) =>
    apiClient.post(`/netsuite/company/connections/${connectionId}/assign-employee/`, { employee_id: employeeId }).then(unwrap),
  removeEmployee: (connectionId, employeeId) =>
    apiClient.post(`/netsuite/company/connections/${connectionId}/remove-employee/${employeeId}/`).then(unwrap),
  testConnection: (connectionId) =>
    apiClient.post(`/netsuite/company/connections/${connectionId}/test/`).then((response) => response.data),
  getMyConnection: () => apiClient.get('/netsuite/my/connection/').then(unwrap),
}

