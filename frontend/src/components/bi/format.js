/**
 * Formatting helpers shared across BI components.
 * Kept local to the BI feature to avoid polluting global utils.
 */

export const formatCurrency = (value, currency = 'USD') =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  }).format(value || 0)

export const formatNumber = (value) =>
  new Intl.NumberFormat('en-US').format(value || 0)

export const formatPercent = (value) =>
  `${Number(value || 0).toFixed(1)}%`

export const formatDate = (value) => {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}
