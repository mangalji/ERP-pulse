/**
 * Shared constants for the Reports Engine frontend.
 */

export const REPORT_TYPES = [
  { value: 'SALES', label: 'Sales Report' },
  { value: 'PURCHASE', label: 'Purchase Report' },
  { value: 'CUSTOMER', label: 'Customer Report' },
  { value: 'VENDOR', label: 'Vendor Report' },
  { value: 'INVENTORY', label: 'Inventory Report' },
  { value: 'FINANCE', label: 'Finance Report' },
  { value: 'INVOICE', label: 'Invoice Report' },
  { value: 'OCR', label: 'OCR Report' },
  { value: 'AI_USAGE', label: 'AI Usage Report' },
  { value: 'NETSUITE_SYNC', label: 'NetSuite Sync Report' },
]

export const REPORT_TYPE_LABEL = Object.fromEntries(REPORT_TYPES.map((t) => [t.value, t.label]))

export const EXPORT_FORMATS = [
  { value: 'CSV', label: 'CSV' },
  { value: 'XLSX', label: 'Excel (.xlsx)' },
  { value: 'PDF', label: 'PDF' },
  { value: 'JSON', label: 'JSON' },
]

export const PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 Days' },
  { value: 'last_30_days', label: 'Last 30 Days' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'year', label: 'Year' },
]

export const SCHEDULE_FREQUENCIES = [
  { value: 'DAILY', label: 'Daily' },
  { value: 'WEEKLY', label: 'Weekly' },
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'QUARTERLY', label: 'Quarterly' },
  { value: 'YEARLY', label: 'Yearly' },
]

export const REPORT_STATUS = {
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  EXPIRED: 'EXPIRED',
}

export const REPORT_STATUS_LABEL = {
  PENDING: 'Pending',
  PROCESSING: 'Processing',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  EXPIRED: 'Expired',
}

export function formatBytes(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDuration(ms) {
  if (!ms) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
