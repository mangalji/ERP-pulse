/**
 * Central date formatting for the whole application.
 *
 * Date only:  05 October 2026
 * Date time:  05 October 2026, 04:20 PM
 *
 * Month names are fixed English names so the output never changes with the
 * browser or operating system locale.
 */

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/

function toDate(value) {
  if (value instanceof Date) return value

  if (typeof value === 'string') {
    // A plain YYYY-MM-DD string is a calendar date, not a moment in time.
    // Build it in local time so it never shifts to the previous day.
    const match = DATE_ONLY_PATTERN.exec(value.trim())
    if (match) {
      return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    }
  }

  return new Date(value)
}

export function formatDate(value, fallback = 'N/A') {
  if (value === null || value === undefined || value === '') return fallback

  const date = toDate(value)
  if (Number.isNaN(date.getTime())) return fallback

  const day = String(date.getDate()).padStart(2, '0')
  return `${day} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`
}

export function formatDateTime(value, fallback = 'N/A') {
  if (value === null || value === undefined || value === '') return fallback

  const date = toDate(value)
  if (Number.isNaN(date.getTime())) return fallback

  const hours24 = date.getHours()
  const hours12 = String(hours24 % 12 || 12).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const period = hours24 >= 12 ? 'PM' : 'AM'

  return `${formatDate(date)}, ${hours12}:${minutes} ${period}`
}