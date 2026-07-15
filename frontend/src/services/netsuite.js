import apiClient, { unwrap } from './apiClient.js'
import { NETSUITE_ENDPOINTS } from '../utils/constants.js'

export const netsuiteApi = {
  getConnectUrl: () => apiClient.get(NETSUITE_ENDPOINTS.connect).then(unwrap),
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
}
