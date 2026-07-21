import { useEffect, useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Input from '../components/ui/Input.jsx'
import Badge from '../components/ui/Badge.jsx'
import PulseIndicator from '../components/ui/PulseIndicator.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'
import Toast, { useToast } from '../components/ui/Toast.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const EMPTY_FORM = {
  client_name: '',
  environment: 'sandbox',
  netsuite_account_id: '',
  client_id: '',
  client_secret: '',
}

const STATUS_TONE = {
  connected: 'positive',
  pending: 'netsuite',
  disconnected: 'neutral',
  error: 'negative',
}

function formatLastSynced(lastSyncedAt) {
  if (!lastSyncedAt) return 'Not synced yet'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(lastSyncedAt).getTime()) / 1000))
  if (seconds < 60) return 'Synced just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `Synced ${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Synced ${hours}h ago`
  const days = Math.floor(hours / 24)
  return `Synced ${days}d ago`
}

export default function ConnectNetSuitePage() {
  const { connectNetSuite, disconnectNetSuite } = useAuth()
  const { toasts, addToast, removeToast } = useToast()

  const [connections, setConnections] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [pendingActionId, setPendingActionId] = useState(null)

  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [isRenaming, setIsRenaming] = useState(false)

  const loadConnections = async () => {
    setIsLoading(true)
    setLoadError('')
    try {
      const data = await netsuiteApi.listConnections()
      setConnections(data)
      const hasActive = data.some((c) => c.is_active && c.status === 'connected')
      if (hasActive) connectNetSuite()
      else disconnectNetSuite()
    } catch (err) {
      setLoadError(err.payload?.message || err.message || 'Failed to load NetSuite connections')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadConnections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFormChange = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))

  const handleAddConnection = async (e) => {
    e.preventDefault()
    setFormError('')
    setIsSubmitting(true)
    try {
      const { authorization_url } = await netsuiteApi.createConnection(form)
      // The user finishes authorizing on NetSuite's own consent screen —
      // once that completes, NetSuite redirects back and the connection
      // is persisted for good, so this only happens once per account.
      window.location.href = authorization_url
    } catch (err) {
      setFormError(err.payload?.message || err.message || 'Failed to start NetSuite connection')
      setIsSubmitting(false)
    }
  }

  const handleSwitch = async (connection) => {
    setPendingActionId(connection.id)
    try {
      await netsuiteApi.switchConnection(connection.id)
      addToast(`${connection.client_name} is now the active connection`, 'success')
      await loadConnections()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to switch connection', 'error')
    } finally {
      setPendingActionId(null)
    }
  }

  const startRename = (connection) => {
    setEditingId(connection.id)
    setEditName(connection.client_name)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditName('')
  }

  const handleRename = async (connection) => {
    const trimmed = editName.trim()
    if (!trimmed || trimmed === connection.client_name) {
      cancelRename()
      return
    }
    setIsRenaming(true)
    try {
      await netsuiteApi.renameConnection(connection.id, trimmed)
      addToast('Connection renamed', 'success')
      cancelRename()
      await loadConnections()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to rename connection', 'error')
    } finally {
      setIsRenaming(false)
    }
  }

  const handleDelete = async (connection) => {
    const confirmed = window.confirm(
      `Remove "${connection.client_name}"? ERP Pulse will no longer be able to read data from this NetSuite account.`
    )
    if (!confirmed) return

    setPendingActionId(connection.id)
    try {
      await netsuiteApi.deleteConnection(connection.id)
      addToast(`${connection.client_name} was removed`, 'success')
      await loadConnections()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to remove connection', 'error')
    } finally {
      setPendingActionId(null)
    }
  }

  return (
    <DashboardLayout title="Connect NetSuite">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 py-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <PulseIndicator state={connections.some((c) => c.is_active) ? 'connected' : 'disconnected'} size="lg" />
          <div>
            <h2 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)] sm:text-3xl">
              Your NetSuite connections
            </h2>
            <p className="mx-auto mt-2 max-w-lg text-sm text-[var(--color-muted)] sm:text-base">
              Enter each account's credentials once — after you approve access on NetSuite's consent
              screen, ERP Pulse stores and refreshes the connection automatically. You won't need to
              reconnect unless you remove it.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : loadError ? (
          <Card className="p-6 text-center text-sm text-[var(--color-negative)]">{loadError}</Card>
        ) : connections.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No NetSuite accounts connected yet"
              description="Connect an account to start pulling live data into ERP Pulse."
            />
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {connections.map((connection) => (
              <Card key={connection.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  {editingId === connection.id ? (
                    <form
                      className="flex items-center gap-2"
                      onSubmit={(e) => {
                        e.preventDefault()
                        handleRename(connection)
                      }}
                    >
                      <input
                        autoFocus
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        disabled={isRenaming}
                        className="w-full max-w-xs rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                      />
                      <Button type="submit" size="sm" isLoading={isRenaming}>
                        Save
                      </Button>
                      <Button intent="ghost" size="sm" type="button" disabled={isRenaming} onClick={cancelRename}>
                        Cancel
                      </Button>
                    </form>
                  ) : (
                    <div className="flex items-center gap-2">
                      <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
                        {connection.client_name}
                      </h3>
                      {connection.is_active && <Badge tone="primary">Active</Badge>}
                      <Badge tone={STATUS_TONE[connection.status] || 'neutral'}>{connection.status}</Badge>
                      <button
                        onClick={() => startRename(connection)}
                        aria-label={`Rename ${connection.client_name}`}
                        title="Rename"
                        className="rounded p-1 text-[var(--color-muted)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
                          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
                        </svg>
                      </button>
                    </div>
                  )}
                  <p className="mt-1 text-xs text-[var(--color-muted)]">
                    Account {connection.netsuite_account_id} · {connection.environment}
                    {connection.status === 'connected' && (
                      <> · {formatLastSynced(connection.last_synced_at)}</>
                    )}
                  </p>
                  {connection.status === 'connected' &&
                    connection.token_expires_in_seconds !== null &&
                    connection.token_expires_in_seconds < 300 && (
                      <p className="mt-1 text-xs text-[var(--color-negative)]">
                        Access token expires very soon — it should refresh automatically on next use.
                      </p>
                    )}
                  {connection.consecutive_failures > 0 && (
                    <p className="mt-1 flex items-start gap-1 text-xs text-[var(--color-negative)]">
                      <span>
                        {connection.consecutive_failures} failed sync
                        {connection.consecutive_failures === 1 ? '' : 's'} in a row
                        {connection.last_error ? `: ${connection.last_error}` : '.'}
                      </span>
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {!connection.is_active && connection.status === 'connected' && (
                    <Button
                      intent="secondary"
                      size="sm"
                      isLoading={pendingActionId === connection.id}
                      onClick={() => handleSwitch(connection)}
                    >
                      Set active
                    </Button>
                  )}
                  <Button
                    intent="ghost"
                    size="sm"
                    className="text-[var(--color-negative)]"
                    isLoading={pendingActionId === connection.id}
                    onClick={() => handleDelete(connection)}
                  >
                    Remove
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {showForm ? (
          <Card className="p-6">
            <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Connect a NetSuite account
            </h3>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Create an Integration record in NetSuite (Setup &gt; Integration &gt; Manage Integrations)
              with the Auth Code Grant enabled to get these values.
            </p>

            {formError && <p className="mt-3 text-sm text-[var(--color-negative)]">{formError}</p>}

            <form className="mt-4 flex flex-col gap-4" onSubmit={handleAddConnection}>
              <Input
                id="clientName"
                label="Connection name"
                placeholder="e.g. Acme Corp — Production"
                value={form.client_name}
                onChange={handleFormChange('client_name')}
                required
              />

              <label className="flex flex-col gap-1.5" htmlFor="environment">
                <span className="text-sm font-medium text-[var(--color-ink-soft)]">Environment</span>
                <select
                  id="environment"
                  value={form.environment}
                  onChange={handleFormChange('environment')}
                  className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </select>
              </label>

              <Input
                id="netsuiteAccountId"
                label="NetSuite Account ID"
                value={form.netsuite_account_id}
                onChange={handleFormChange('netsuite_account_id')}
                required
              />
              <Input
                id="clientId"
                label="Client ID"
                value={form.client_id}
                onChange={handleFormChange('client_id')}
                required
              />
              <Input
                id="clientSecret"
                label="Client Secret"
                type="password"
                value={form.client_secret}
                onChange={handleFormChange('client_secret')}
                required
              />

              <div className="flex items-center gap-3">
                <Button type="submit" isLoading={isSubmitting}>
                  {isSubmitting ? 'Redirecting...' : 'Continue to NetSuite'}
                </Button>
                <Button intent="ghost" type="button" onClick={() => setShowForm(false)} disabled={isSubmitting}>
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <Button intent="netsuite" size="lg" className="mx-auto" onClick={() => setShowForm(true)}>
            Connect a NetSuite account
          </Button>
        )}
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </DashboardLayout>
  )
}
