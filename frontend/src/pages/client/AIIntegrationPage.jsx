import { useEffect, useMemo, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Badge from '../../components/ui/Badge.jsx'
import { aiIntegrationApi } from '../../services/aiIntegration.js'

const EMPTY_FORM = {
  provider: '',
  model: '',
  api_key: '',
}

export default function AIIntegrationPage() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState({})
  const [connected, setConnected] = useState(false)
  const [apiKeySet, setApiKeySet] = useState(false)
  const [lastTestedAt, setLastTestedAt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const providerModels = useMemo(
    () => models?.[form.provider] || [],
    [models, form.provider],
  )

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [providerData, configData] = await Promise.all([
        aiIntegrationApi.getProviders(),
        aiIntegrationApi.getConfig(),
      ])

      setProviders(providerData?.providers || [])
      setModels(providerData?.models || {})

      const config = configData || {}
      setForm({
        provider: config.provider || '',
        model: config.model || '',
        api_key: '',
      })
      setConnected(Boolean(config.connected))
      setApiKeySet(Boolean(config.api_key_set))
      setLastTestedAt(config.last_tested_at || null)
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to load AI integration settings.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const changeProvider = (provider) => {
    const firstModel = models?.[provider]?.[0]?.value || ''
    setForm((current) => ({
      ...current,
      provider,
      model: firstModel,
    }))
    setMessage('')
    setError('')
  }

  const handleTest = async () => {
    setBusy('test')
    setMessage('')
    setError('')
    try {
      const result = await aiIntegrationApi.test({
        provider: form.provider,
        model: form.model,
        ...(form.api_key ? { api_key: form.api_key } : {}),
      })
      setMessage(result?.message || 'Connection test successful.')
      setLastTestedAt(new Date().toISOString())
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'AI provider connection test failed.',
      )
    } finally {
      setBusy('')
    }
  }

  const handleConnect = async () => {
    setBusy('connect')
    setMessage('')
    setError('')
    try {
      const result = await aiIntegrationApi.connect(form)
      setConnected(Boolean(result?.connected))
      setApiKeySet(Boolean(result?.api_key_set))
      setMessage(result?.message || 'AI provider connected successfully.')
      setForm((current) => ({ ...current, api_key: '' }))
      setLastTestedAt(result?.last_tested_at || new Date().toISOString())
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to connect the AI provider.',
      )
    } finally {
      setBusy('')
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect the configured AI provider?')) return

    setBusy('disconnect')
    setMessage('')
    setError('')
    try {
      const result = await aiIntegrationApi.disconnect()
      setConnected(false)
      setApiKeySet(false)
      setForm((current) => ({ ...current, api_key: '' }))
      setMessage(result?.message || 'AI provider disconnected successfully.')
      setLastTestedAt(null)
    } catch (err) {
      setError(
        err?.payload?.message ||
          err?.message ||
          'Unable to disconnect the AI provider.',
      )
    } finally {
      setBusy('')
    }
  }

  const handleReset = () => {
    setForm({
      provider: '',
      model: '',
      api_key: '',
    })
    setMessage('')
    setError('')
  }

  return (
    <ClientLayout
      title="AI Integration"
      breadcrumb="Settings / AI Integration"
    >
      <div className="mx-auto max-w-3xl">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold text-[var(--color-ink)]">
                AI Integration
              </h1>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Configure the AI provider used by your company&apos;s OCR.
              </p>
            </div>

            <Badge tone={connected ? 'positive' : 'neutral'}>
              {connected ? 'Connected' : 'Not connected'}
            </Badge>
          </div>

          {loading ? (
            <div className="py-10 text-sm text-[var(--color-muted)]">
              Loading AI configuration...
            </div>
          ) : (
            <div className="mt-6 space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--color-ink)]">
                  AI Provider
                </label>
                <select
                  value={form.provider}
                  onChange={(event) => changeProvider(event.target.value)}
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
                  disabled={busy !== ''}
                >
                  <option value="">Select provider</option>
                  {providers.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--color-ink)]">
                  AI Model
                </label>
                <select
                  value={form.model}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      model: event.target.value,
                    }))
                  }
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
                  disabled={!form.provider || busy !== ''}
                >
                  <option value="">Select model</option>
                  {providerModels.map((model) => (
                    <option key={model.value} value={model.value}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-[var(--color-ink)]">
                  API Key
                </label>
                <input
                  type="password"
                  value={form.api_key}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      api_key: event.target.value,
                    }))
                  }
                  placeholder={
                    apiKeySet
                      ? 'Saved securely — enter a new key to replace it'
                      : 'Enter provider API key'
                  }
                  autoComplete="new-password"
                  className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm"
                  disabled={busy !== ''}
                />
              </div>

              {lastTestedAt && (
                <p className="text-xs text-[var(--color-muted)]">
                  Last tested: {new Date(lastTestedAt).toLocaleString()}
                </p>
              )}

              {message && (
                <div className="rounded-md bg-[var(--color-positive-soft)] px-3 py-2 text-sm text-[var(--color-positive)]">
                  {message}
                </div>
              )}

              {error && (
                <div className="rounded-md bg-[var(--color-danger-soft)] px-3 py-2 text-sm text-[var(--color-danger)]">
                  {error}
                </div>
              )}

              <div className="flex flex-wrap gap-3 pt-2">
                <Button
                  type="button"
                  onClick={handleTest}
                  disabled={!form.provider || !form.model || busy !== ''}
                >
                  {busy === 'test' ? 'Testing...' : 'Test'}
                </Button>

                <Button
                  type="button"
                  onClick={handleReset}
                  disabled={busy !== ''}
                >
                  Reset
                </Button>

                {connected ? (
                  <Button
                    type="button"
                    onClick={handleDisconnect}
                    disabled={busy !== ''}
                  >
                    {busy === 'disconnect' ? 'Disconnecting...' : 'Disconnect'}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    onClick={handleConnect}
                    disabled={
                      !form.provider ||
                      !form.model ||
                      !form.api_key ||
                      busy !== ''
                    }
                  >
                    {busy === 'connect' ? 'Connecting...' : 'Connect'}
                  </Button>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>
    </ClientLayout>
  )
}
