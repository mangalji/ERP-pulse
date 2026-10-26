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
  const [form, setForm] = useState({ provider: 'GOOGLE', mailbox_email: '', display_name: '', ocr_template_id: '', client_id: '', client_secret: '' })
  const [syncFrom, setSyncFrom] = useState('')
  const [syncSetupId, setSyncSetupId] = useState(null)
  const [syncBusy, setSyncBusy] = useState(false)
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
  return <ClientLayout>
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div><h1 className="text-2xl font-semibold">Email Integration</h1><p className="text-sm text-[var(--color-text-muted)]">Connect a mailbox once. New emails are checked automatically and vendor bills continue through OCR, validation and NetSuite posting.</p></div>
      {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}
      {integrations.filter(item => item.is_active && item.status === 'ERROR').map(item => <EmailReconnectBanner key={item.id} integration={item} />)}
      <Card className="p-5"><h2 className="mb-4 text-lg font-semibold">Connect mailbox</h2><form onSubmit={connect} className="grid gap-3 md:grid-cols-2">
        <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className="rounded border p-2"><option value="GOOGLE">Google Gmail</option><option value="ZOHO">Zoho Mail</option></select>
        <Input required placeholder="Mailbox email" value={form.mailbox_email} onChange={e => setForm({ ...form, mailbox_email: e.target.value })} />
        <Input placeholder="Display name" value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
        <Input required placeholder="OAuth Client ID" autoComplete="off" value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} />
        <Input required type="password" placeholder="OAuth Client Secret" autoComplete="new-password" value={form.client_secret} onChange={e => setForm({ ...form, client_secret: e.target.value })} />
        <select required value={form.ocr_template_id} onChange={e => setForm({ ...form, ocr_template_id: e.target.value })} className="rounded border p-2"><option value="">Select OCR template</option>{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        {form.provider === 'ZOHO' && <select value={form.zoho_data_center || 'IN'} onChange={e => setForm({ ...form, zoho_data_center: e.target.value })} className="rounded border p-2"><option value="IN">India</option><option value="COM">United States</option><option value="EU">Europe</option><option value="COM_AU">Australia</option><option value="JP">Japan</option><option value="CA">Canada</option></select>}
        <div><Button type="submit">Connect and authorize</Button></div>
      </form></Card>
      <div className="space-y-3">{loading ? <p>Loading…</p> : integrations.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><strong>{item.display_name || item.mailbox_email}</strong><p className="text-sm">{item.provider} · {item.mailbox_email} · {item.status}{item.is_active ? ' · Active' : ''}{item.is_paused ? ' · Processing stopped' : ''}</p><p className="text-xs text-[var(--color-text-muted)]">Last sync: {item.last_successful_sync_at ? new Date(item.last_successful_sync_at).toLocaleString() : 'Not started'}</p></div><div className="flex flex-wrap gap-2">{item.status !== 'CONNECTED' ? <Button onClick={async () => { try { const r = await emailIntegrationApi.reconnect(item.id); window.location.assign(r.authorization_url) } catch (e) { setError(e?.payload?.message || e?.message || 'Could not reconnect.') } }}>Reconnect</Button> : <>{!item.is_active && <Button onClick={async () => { try { await emailIntegrationApi.activate(item.id); await load() } catch (e) { setError(e?.payload?.message || e?.message || 'Could not activate mailbox.') } }}>Make active</Button>}{item.is_active && !item.initial_sync_configured && syncSetupId !== item.id && <Button disabled={syncBusy} onClick={() => startSyncSetup(item.id)}>Start automatic sync</Button>}{item.initial_sync_configured && <Button disabled={syncBusy || (item.is_paused && !item.is_active)} onClick={() => changeConnection(item.id, item.is_paused ? 'resume' : 'pause')}>{item.is_paused ? 'Start email fetching' : 'Stop email fetching'}</Button>}</>}{item.status !== 'DISCONNECTED' && <Button disabled={syncBusy} onClick={() => changeConnection(item.id, 'disconnect')}>Disconnect</Button>}</div></div>{item.status === 'CONNECTED' && item.is_active && !item.initial_sync_configured && syncSetupId === item.id && <form onSubmit={e => configure(e, item.id)} className="mt-4 flex flex-wrap items-end gap-2"><Input label="Process emails received from (your local time)" type="datetime-local" required value={syncFrom} onChange={e => setSyncFrom(e.target.value)}/><Button type="submit" disabled={syncBusy}>Start sync</Button><Button type="button" disabled={syncBusy} onClick={() => { setSyncSetupId(null); setError('') }}>Cancel</Button><p className="self-center text-sm text-[var(--color-text-muted)]">Checks every 30 minutes after starting.</p></form>}{item.last_error && <p className="mt-2 text-sm text-red-600">{item.last_error}</p>}</Card>)}</div>
    </div>
  </ClientLayout>
}

