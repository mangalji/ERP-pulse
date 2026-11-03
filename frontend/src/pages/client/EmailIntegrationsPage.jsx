import { useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import apiClient, { unwrap } from '../../services/apiClient.js'
import { emailIntegrationApi } from '../../services/emailIntegration.js'
import EmailReconnectBanner from '../../components/EmailReconnectBanner.jsx'

export default function EmailIntegrationsPage() {
  const [integrations, setIntegrations] = useState([])
  const [templates, setTemplates] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ provider: 'GOOGLE', mailbox_email: '', display_name: '', ocr_template_id: '', client_id: '', client_secret: '' })
  const [syncFrom, setSyncFrom] = useState('')
  const [syncSetupId, setSyncSetupId] = useState(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncDetailsId, setSyncDetailsId] = useState(null)
  const [processingHealth, setProcessingHealth] = useState(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const load = async () => {
    setLoading(true); setError('')
    try {
      const [mailboxes, templateData] = await Promise.all([
        emailIntegrationApi.list(), apiClient.get('/ocr/extraction-templates/').then(unwrap),
      ])
      setIntegrations(mailboxes || [])
      setTemplates(templateData?.results || templateData || [])
    } catch (e) { setError(e?.payload?.message || e?.message || 'Could not load email integrations.') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  const connect = async (event) => {
    event.preventDefault(); setError('')
    try {
      const payload = { ...form, ocr_template_id: form.ocr_template_id || null }
      if (!payload.client_id && !payload.client_secret) { delete payload.client_id; delete payload.client_secret }
      if (payload.provider !== 'ZOHO') delete payload.zoho_data_center
      const result = await emailIntegrationApi.connect(payload)
      window.location.assign(result.authorization_url)
    } catch (e) { setError(e?.payload?.message || e?.message || 'Could not start mailbox authorization.') }
  }
  const startSyncSetup = async (id) => {
    setError(''); setSyncBusy(true)
    try { await emailIntegrationApi.checkSyncReadiness(id); setSyncFrom(''); setSyncSetupId(id) }
    catch (e) { setError(e?.payload?.message || e?.message || 'Could not check email sync readiness.') }
    finally { setSyncBusy(false) }
  }
  const configure = async (event, id) => {
    event.preventDefault(); setError('')
    const start = new Date(syncFrom)
    if (!syncFrom || Number.isNaN(start.getTime()) || start > new Date()) {
      setError('Choose a valid date and time that is not in the future.')
      return
    }
    setSyncBusy(true)
    try { await emailIntegrationApi.configureInitialSync(id, { initial_sync_from_at: start.toISOString() }); setSyncSetupId(null); await load() }
    catch (e) { setError(e?.payload?.message || e?.message || 'Could not start automatic email processing.') }
    finally { setSyncBusy(false) }
  }
  const changeConnection = async (id, action) => {
    if (action === 'disconnect' && !window.confirm('Disconnect this mailbox? Automatic processing will stop. After reconnecting, choose a new starting date and time.')) return
    setError(''); setSyncBusy(true)
    try { await emailIntegrationApi[action](id); setSyncSetupId(null); await load() }
    catch (e) { setError(e?.payload?.message || e?.message || 'Could not update mailbox connection.') }
    finally { setSyncBusy(false) }
  }
  const toggleSyncDetails = async (id) => {
    if (syncDetailsId === id) {
      setSyncDetailsId(null)
      return
    }
    setSyncDetailsId(id)
    setHealthLoading(true)
    try {
      setProcessingHealth(await emailIntegrationApi.health())
    } catch {
      setProcessingHealth({ worker_running: false, scheduler_running: false, message: 'Status could not be verified.' })
    } finally { setHealthLoading(false) }
  }
  return <ClientLayout>
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">Email Integration</h1><p className="mt-1 text-sm text-[var(--color-muted)]">Connect a mailbox once.</p></div><Button onClick={() => { setShowForm(true); setError('') }}>New Connection</Button></div>
      {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}
      {integrations.filter(item => item.is_active && item.status === 'ERROR').map(item => <EmailReconnectBanner key={item.id} integration={item} />)}
      {showForm && <Card className="w-full p-6"><h2 className="mb-4 text-base font-semibold text-[var(--color-ink)]">Create Connection</h2><form onSubmit={connect} className="grid gap-3 md:grid-cols-2">
        <select aria-label="Email provider" value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="GOOGLE">Google Gmail</option><option value="ZOHO">Zoho Mail</option></select>
        <Input required placeholder="Mailbox email" value={form.mailbox_email} onChange={e => setForm({ ...form, mailbox_email: e.target.value })} />
        <Input placeholder="Display name" value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
        <Input required placeholder="OAuth Client ID" autoComplete="off" value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} />
        <Input required type="password" placeholder="OAuth Client Secret" autoComplete="new-password" value={form.client_secret} onChange={e => setForm({ ...form, client_secret: e.target.value })} />
        <select aria-label="OCR template" required value={form.ocr_template_id} onChange={e => setForm({ ...form, ocr_template_id: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="">Select OCR template</option>{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        {form.provider === 'ZOHO' && <select aria-label="Zoho data center" value={form.zoho_data_center || 'IN'} onChange={e => setForm({ ...form, zoho_data_center: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="IN">India</option><option value="COM">United States</option><option value="EU">Europe</option><option value="COM_AU">Australia</option><option value="JP">Japan</option><option value="CA">Canada</option></select>}
        <div className="flex flex-wrap gap-2 md:col-span-2"><Button type="submit">Connect and authorize</Button><Button type="button" intent="secondary" onClick={() => { setShowForm(false); setForm({ provider: 'GOOGLE', mailbox_email: '', display_name: '', ocr_template_id: '', client_id: '', client_secret: '' }); setError('') }}>Cancel</Button></div>
      </form></Card>}
      {!loading && integrations.length === 0 && <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">No email connections yet. Create one to get started.</p></Card>}
    <div className="space-y-3">{loading ? <p>Loading…</p> : integrations.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><strong>{item.display_name || item.mailbox_email}</strong><p className="text-sm">{item.provider} · {item.mailbox_email} · {item.status}{item.is_active ? ' · Active' : ''}{item.is_paused ? ' · Processing stopped' : ''}</p></div><div className="flex flex-wrap gap-2">{item.status !== 'CONNECTED' ? <Button onClick={async () => { try { const r = await emailIntegrationApi.reconnect(item.id); window.location.assign(r.authorization_url) } catch (e) { setError(e?.payload?.message || e?.message || 'Could not reconnect.') } }}>Reconnect</Button> : <>{!item.is_active && <Button onClick={async () => { try { await emailIntegrationApi.activate(item.id); await load() } catch (e) { setError(e?.payload?.message || e?.message || 'Could not activate mailbox.') } }}>Active</Button>}{item.is_active && item.initial_sync_configured && <Button intent="secondary" disabled={healthLoading} onClick={() => toggleSyncDetails(item.id)}>Sync details</Button>}{item.is_active && !item.initial_sync_configured && syncSetupId !== item.id && <Button disabled={syncBusy} onClick={() => startSyncSetup(item.id)}>Start automatic sync</Button>}{item.is_active && item.initial_sync_configured && <Button disabled={syncBusy} onClick={() => changeConnection(item.id, item.is_paused ? 'resume' : 'pause')}>{item.is_paused ? 'Start email fetching' : 'Stop email fetching'}</Button>}</>}{item.status !== 'DISCONNECTED' && <Button disabled={syncBusy} onClick={() => changeConnection(item.id, 'disconnect')}>Disconnect</Button>}</div></div>{item.is_active && syncDetailsId === item.id && <SyncDetails item={item} health={processingHealth} loading={healthLoading} />}{item.status === 'CONNECTED' && item.is_active && !item.initial_sync_configured && syncSetupId === item.id && <form onSubmit={e => configure(e, item.id)} className="mt-4 flex flex-wrap items-end gap-2"><Input label="Process emails received from (your local time)" type="datetime-local" required value={syncFrom} onChange={e => setSyncFrom(e.target.value)}/><Button type="submit" disabled={syncBusy}>Start sync</Button><Button type="button" disabled={syncBusy} onClick={() => { setSyncSetupId(null); setError('') }}>Cancel</Button><p className="self-center text-sm text-[var(--color-text-muted)]">Checks every 5 minutes after starting.</p></form>}{item.last_error && <p className="mt-2 text-sm text-red-600">{item.last_error}</p>}</Card>)}</div>
    </div>
  </ClientLayout>
}

function SyncDetails({ item, health, loading }) {
  const summary = item.last_sync_summary || {}
  const dateTime = (value) => value ? new Date(value).toLocaleString() : 'Not available yet'
  const status = (isRunning) => isRunning ? 'Running' : 'Unavailable'
  return <div className="mt-4 grid gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 text-sm md:grid-cols-2">
    <Detail label="Last successful mailbox check" value={dateTime(item.last_successful_sync_at)} />
    <Detail label="Next automatic mailbox check" value={item.is_paused ? 'Paused' : dateTime(item.next_sync_at)} />
    <Detail label="Fetch email difference" value={`Every ${item.sync_interval_minutes} minutes`} />
    <Detail label="Worker status" value={loading ? 'Checking…' : status(health?.worker_running)} tone={loading ? undefined : health?.worker_running ? 'success' : 'error'} />
    <Detail label="Scheduler status" value={loading ? 'Checking…' : status(health?.scheduler_running)} tone={loading ? undefined : health?.scheduler_running ? 'success' : 'error'} />
    <Detail label="Latest processing result" value={summary.completed_at ? `${summary.emails_fetched || 0} email(s) fetched, ${summary.vendor_bill_records_created || 0} vendor-bill record(s) created, ${summary.emails_ignored || 0} ignored` : 'No completed sync yet'} />
    {health?.message && <p className="md:col-span-2 text-xs text-[var(--color-text-muted)]">{health.message}</p>}
  </div>
}

function Detail({ label, value, tone }) {
  return <div><p className="text-xs text-[var(--color-text-muted)]">{label}</p><p className={tone === 'error' ? 'mt-1 font-medium text-red-600' : tone === 'success' ? 'mt-1 font-medium text-emerald-600' : 'mt-1 font-medium text-[var(--color-ink)]'}>{value}</p></div>
}

