import Badge from '../ui/Badge.jsx'
import { REPORT_STATUS_LABEL } from './constants.js'

const TONE_MAP = {
  PENDING: 'neutral',
  PROCESSING: 'netsuite',
  COMPLETED: 'positive',
  FAILED: 'negative',
  EXPIRED: 'neutral',
}

/**
 * Report status badge. Supports PENDING / PROCESSING / COMPLETED /
 * FAILED / EXPIRED. Falls back to neutral for unknown statuses.
 */
export default function StatusBadge({ status }) {
  const key = String(status || '').toUpperCase()
  const tone = TONE_MAP[key] || 'neutral'
  return <Badge tone={tone}>{REPORT_STATUS_LABEL[key] || status || '—'}</Badge>
}
