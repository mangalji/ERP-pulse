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

const getFriendlyError = (err, fallback) => {
  const message =
    err?.payload?.message ||
    err?.response?.data?.message

  return typeof message === 'string' && message.trim()
    ? message
    : fallback
}

export default function AIIntegrationPage() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState({})
  const [connected, setConnected] = useState(false)
  const [apiKeySet, setApiKeySet] = useState(false)
  const [savedProvider, setSavedProvider] = useState('')
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
      const configuredProvider = config.provider || ''

      setForm({
        provider: configuredProvider,
        model: config.model || '',
        api_key: '',
      })
      setConnected(Boolean(config.connected))
      setApiKeySet(Boolean(config.api_key_set))
      setSavedProvider(configuredProvider)
      setLastTestedAt(config.last_tested_at || null)
    } catch (err) {
      setError(
        getFriendlyError(
          err,
          'Unable to load AI integration settings. Please try again.',
        ),
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

  const handleRefreshModels = async () => {
    if (!form.provider) {
      setError('Please select an AI provider first.')
      return
    }

    const canUseSavedKey =
      Boolean(apiKeySet) && savedProvider === form.provider

    if (!form.api_key && !canUseSavedKey) {
      setError(
        'Please enter the API key for this provider before refreshing models.',
      )
      return
    }

    setBusy('refresh')
    setMessage('')
    setError('')

    try {
      const result = await aiIntegrationApi.refreshModels({
        provider: form.provider,
        ...(form.api_key ? { api_key: form.api_key } : {}),
      })

      const refreshedModels = Array.isArray(result?.models)
        ? result.models
        : []

      setModels((current) => ({
        ...current,
        [form.provider]: refreshedModels,
      }))

      setForm((current) => ({
        ...current,
        model: refreshedModels.some(
          (item) => item.value === current.model,
        )
          ? current.model
          : refreshedModels[0]?.value || '',
      }))

      setMessage(
        result?.message ||
          `${result?.count || refreshedModels.length} model(s) refreshed successfully.`,
      )
    } catch (err) {
      setError(
        getFriendlyError(
          err,
          'We couldn’t refresh the AI model list. Please try again.',
        ),
      )
    } finally {
      setBusy('')
    }
  }

  const handleTest = async () => {
    if (!form.provider) {
      setError('Please select an AI provider first.')
      return
    }

    if (!form.model) {
      setError('Please select an AI model first.')
      return
    }

    if (!form.api_key && !(apiKeySet && savedProvider === form.provider)) {
      setError(
        'Please enter the API key for this provider before testing the connection.',
      )
      return
    }

    setBusy('test')
    setMessage('')
    setError('')

    try {
      const result = await aiIntegrationApi.test({
        provider: form.provider,
        model: form.model,
        ...(form.api_key ? { api_key: form.api_key } : {}),
      })

      setMessage(
        result?.message || 'AI connection test successful.',
      )
      setLastTestedAt(new Date().toISOString())
    } catch (err) {
      setError(
        getFriendlyError(
          err,
          'We couldn’t verify the AI connection. Please check the API key and model.',
        ),
      )
    } finally {
      setBusy('')
    }
  }

  const handleConnect = async () => {
    if (!form.provider) {
      setError('Please select an AI provider first.')
      return
    }

    if (!form.model) {
      setError('Please select an AI model first.')
      return
    }

    if (!form.api_key) {
      setError(
        'Please enter the API key before connecting the AI provider.',
      )
      return
    }

    setBusy('connect')
    setMessage('')
    setError('')

    try {
      const result = await aiIntegrationApi.connect(form)

      setConnected(Boolean(result?.connected))
      setApiKeySet(Boolean(result?.api_key_set))
      setSavedProvider(form.provider)
      setMessage(
        result?.message || 'AI provider connected successfully.',
      )
      setForm((current) => ({ ...current, api_key: '' }))
      setLastTestedAt(
        result?.last_tested_at || new Date().toISOString(),
      )
    } catch (err) {
      setError(
        getFriendlyError(
          err,
          'We couldn’t connect the AI provider. Please check your configuration and try again.',
        ),
      )
    } finally {
      setBusy('')
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect the configured AI provider?')) {
      return
    }

    setBusy('disconnect')
    setMessage('')
    setError('')

    try {
      const result = await aiIntegrationApi.disconnect()

      setConnected(false)
      setApiKeySet(false)
      setSavedProvider('')
      setForm((current) => ({ ...current, api_key: '' }))
      setMessage(
        result?.message || 'AI provider disconnected successfully.',
      )
      setLastTestedAt(null)
    } catch (err) {
      setError(
        getFriendlyError(
          err,
          'We couldn’t disconnect the AI provider. Please try again.',
        ),
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
                Configure the AI provider and model used by your company&apos;s AI features.
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
                <div className="mb-2 flex items-center justify-between gap-3">
                  <label className="block text-sm font-medium text-[var(--color-ink)]">
                    AI Model
                  </label>

                  <Button
                    type="button"
                    onClick={handleRefreshModels}
                    disabled={!form.provider || busy !== ''}
                  >
                    {busy === 'refresh' ? 'Refreshing...' : 'Refresh Models'}
                  </Button>
                </div>

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
                  <option value="">
                    {providerModels.length
                      ? 'Select model'
                      : 'No models loaded — refresh to load models'}
                  </option>

                  {providerModels.map((model) => (
                    <option key={model.value} value={model.value}>
                      {model.label}
                    </option>
                  ))}
                </select>

                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Refresh the list to fetch models currently available from the selected provider.
                </p>
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
                  disabled={
                    !form.provider ||
                    !form.model ||
                    busy !== ''
                  }
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
                    {busy === 'disconnect'
                      ? 'Disconnecting...'
                      : 'Disconnect'}
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
                    {busy === 'connect'
                      ? 'Connecting...'
                      : 'Connect'}
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
