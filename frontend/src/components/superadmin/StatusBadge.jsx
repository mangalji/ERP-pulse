import Badge from '../ui/Badge.jsx'

/**
 * Maps a business status string to a visual tone.
 * Used consistently across all superadmin tables and cards.
 */
const STATUS_TONE = {
  ACTIVE: 'positive',
  TRIAL: 'primary',
  SUSPENDED: 'negative',
  EXPIRED: 'neutral',
  CANCELLED: 'negative',
  INACTIVE: 'neutral',
  ARCHIVED: 'neutral',
  ENDED: 'neutral',
  true: 'positive',
  false: 'neutral',
}

export default function StatusBadge({ status }) {
  const key = status === true || status === false ? String(status) : status
  const tone = STATUS_TONE[key] || 'neutral'
  const label = status === true ? 'Enabled' : status === false ? 'Disabled' : status || 'Unknown'
  return <Badge tone={tone}>{label}</Badge>
}
