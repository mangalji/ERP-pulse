import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { netsuiteApi } from '../../services/netsuite.js'
import { isCompanyAdminUser } from '../../utils/netsuiteErrors.js'

/**
 * Shown when NetSuite rejects our stored authorization. Tells the person
 * what happened in plain language and what THEY can do:
 *  - Company Admin: a Reconnect button (straight to NetSuite consent when
 *    the connection is known, otherwise to the connections page).
 *  - Everyone else: who to ask. They cannot reconnect themselves.
 */
export default function NetSuiteReauthBanner({ connectionId = null }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState('')
  const isAdmin = isCompanyAdminUser(user)

  const reconnect = async () => {
    if (!connectionId) {
      navigate('/app/integrations/netsuite')
      return
    }

    setBusy(true)
    setFailure('')
    try {
      const result = await netsuiteApi.reconnectConnection(connectionId)
      if (!result?.authorization_url) {
        throw new Error('NetSuite did not return an authorization link.')
      }
      window.location.href = result.authorization_url
    } catch (err) {
      setFailure(
        err?.response?.data?.detail ||
          err?.message ||
          'Could not start the reconnect. Please try again.',
      )
      setBusy(false)
    }
  }

  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium">NetSuite needs to be reconnected</p>
        <p className="mt-1">
          {isAdmin
            ? 'The NetSuite authorization has expired or was disconnected. Fields cannot be refreshed and documents cannot be validated or posted until you reconnect.'
            : 'The NetSuite authorization has expired or was disconnected. Please ask your Company Admin to reconnect NetSuite, then try again.'}
        </p>
        {failure && <p className="mt-1 text-red-700">{failure}</p>}
      </div>

      {isAdmin && (
        <Button
          type="button"
          intent="primary"
          size="sm"
          onClick={reconnect}
          isLoading={busy}
        >
          Reconnect NetSuite
        </Button>
      )}
    </div>
  )
}