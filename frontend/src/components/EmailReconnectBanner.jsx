import { useEffect, useState } from 'react'
import Button from './ui/Button.jsx'
import { emailIntegrationApi } from '../services/emailIntegration.js'

export default function EmailReconnectBanner({ integration }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const reconnect = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await emailIntegrationApi.reconnect(integration.id)
      if (!result?.authorization_url) throw new Error('Authorization link is unavailable.')
      window.location.assign(result.authorization_url)
    } catch (err) {
      setError(err?.payload?.message || err.message || 'Could not start reconnect.')
      setBusy(false)
    }
  }

  return <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
    <div>
      <p className="font-medium">Email connection needs to be reconnected</p>
      <p>{integration.mailbox_email}: automatic email fetching is paused until you reconnect.</p>
      {error && <p className="text-red-700">{error}</p>}
    </div>
    <Button type="button" onClick={reconnect} isLoading={busy}>Reconnect</Button>
  </div>
}

export function ActiveEmailReconnectNotice() {
  const [integration, setIntegration] = useState(null)
  useEffect(() => {
    let mounted = true
    emailIntegrationApi.list().then(items => {
      if (mounted) setIntegration((items || []).find(item => item.is_active && item.status === 'ERROR') || null)
    }).catch(() => {})
    return () => { mounted = false }
  }, [])
  return integration ? <EmailReconnectBanner integration={integration} /> : null
}
