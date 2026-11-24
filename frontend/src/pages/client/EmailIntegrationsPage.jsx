import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import { emailIntegrationApi } from '../../services/emailIntegration.js'
import { ocrApi } from '../../services/ocr.js'
import EmailReconnectBanner from '../../components/EmailReconnectBanner.jsx'
import DateInput from '../../components/ui/DateInput.jsx'
import { formatDateTime } from '../../utils/formatDate.js'

export default function EmailIntegrationsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { integrationId } = useParams()
  const isNewPage = location.pathname.endsWith('/new')
  const [integrations, setIntegrations] = useState([])
  const [templates, setTemplates] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ provider: 'GOOGLE', mailbox_email: '', display_name: '', ocr_template_id: '', client_id: '', client_secret: '' })
  const [schedule, setSchedule] = useState(createDefaultSchedule)
  const [fetchFrom, setFetchFrom] = useState(createDefaultFetchFrom)
  const [fetchBoundary, setFetchBoundary] = useState(null)
  const [syncSetupId, setSyncSetupId] = useState(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncDetailsId, setSyncDetailsId] = useState(null)
  const load = async () => {
    setLoading(true); setError('')
    try {
      const [mailboxes, templates] = await Promise.all([
        emailIntegrationApi.list(), ocrApi.listExtractionTemplates(),
      ])
      setIntegrations(mailboxes || [])
      setTemplates(templates)
    } catch (e) { setError(e?.payload?.message || e?.message || 'Could not load email integrations.') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const connectedIntegrationId = params.get('email') === 'connected' ? params.get('integration') : null
    if (connectedIntegrationId) startSyncSetup(connectedIntegrationId)
  }, [location.search])
  const visibleIntegrations = integrationId
    ? integrations.filter((item) => String(item.id) === String(integrationId))
    : integrations
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
    setError(''); setSyncBusy(true); setSchedule(createDefaultSchedule()); setFetchFrom(createDefaultFetchFrom()); setFetchBoundary(null); setSyncSetupId(id)
    try {
      const result = await emailIntegrationApi.fetchBoundary(id)
      const boundary = result?.latest_fetched_email_received_at || null
      setFetchBoundary(boundary)
      setFetchFrom(createDefaultFetchFrom(boundary))
    } catch (e) {
      setError(e?.payload?.message || e?.message || 'Could not check this mailbox’s prior fetch history.')
    } finally { setSyncBusy(false) }
  }
  const configure = async (event, id) => {
    event.preventDefault(); setError('')
    setSyncBusy(true)
    try { await emailIntegrationApi.configureInitialSync(id, { schedule, fetch_from: fetchFrom }); setSyncSetupId(null); await load() }
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
  const deleteIntegration = async (item) => {
    if (!window.confirm(`Delete ${item.mailbox_email}? This permanently removes its saved mailbox connection and sync state.`)) return
    setError(''); setSyncBusy(true)
    try { await emailIntegrationApi.delete(item.id); await load() }
    catch (e) { setError(e?.payload?.message || e?.message || 'Could not delete mailbox connection.') }
    finally { setSyncBusy(false) }
  }
  const toggleSyncDetails = (id) => {
    if (syncDetailsId === id) {
      setSyncDetailsId(null)
      return
    }
    setSyncDetailsId(id)
  }
  return <ClientLayout>
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">{isNewPage ? 'New Email Connection' : integrationId ? 'Email Connection Details' : 'Email Integration'}</h1><p className="mt-1 text-sm text-[var(--color-muted)]">Connect and manage company mailboxes.</p></div>{isNewPage || integrationId ? <Button intent="secondary" onClick={() => navigate('/app/integrations/email')}>Back to Connections</Button> : <Button onClick={() => { setError(''); navigate('/app/integrations/email/new') }}>New Connection</Button>}</div>
      {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}
      {integrations.filter(item => item.is_active && item.status === 'ERROR').map(item => <EmailReconnectBanner key={item.id} integration={item} />)}
      {isNewPage && <Card className="w-full p-6"><h2 className="mb-4 text-base font-semibold text-[var(--color-ink)]">Create Connection</h2><form onSubmit={connect} className="grid gap-3 md:grid-cols-2">
        <select aria-label="Email provider" value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="GOOGLE">Google Gmail</option><option value="ZOHO">Zoho Mail</option><option value="OUTLOOK">Microsoft Outlook</option></select>
        <Input required placeholder="Mailbox email" value={form.mailbox_email} onChange={e => setForm({ ...form, mailbox_email: e.target.value })} />
        <Input placeholder="Display name" value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
        <Input required placeholder="OAuth Client ID" autoComplete="off" value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })} />
        <Input required type="password" placeholder="OAuth Client Secret" autoComplete="new-password" value={form.client_secret} onChange={e => setForm({ ...form, client_secret: e.target.value })} />
        <select aria-label="OCR template" required value={form.ocr_template_id} onChange={e => setForm({ ...form, ocr_template_id: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="">Select OCR template</option>{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        {form.provider === 'ZOHO' && <select aria-label="Zoho data center" value={form.zoho_data_center || 'IN'} onChange={e => setForm({ ...form, zoho_data_center: e.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-[var(--color-ink)]"><option value="IN">India</option><option value="COM">United States</option><option value="EU">Europe</option><option value="COM_AU">Australia</option><option value="JP">Japan</option><option value="CA">Canada</option></select>}
        <div className="flex flex-wrap gap-2 md:col-span-2"><Button type="submit">Connect and authorize</Button><Button type="button" intent="secondary" onClick={() => navigate('/app/integrations/email')}>Cancel</Button></div>
      </form></Card>}
      {!isNewPage && !loading && visibleIntegrations.length === 0 && <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">{integrationId ? 'Email connection not found.' : 'No email connections yet. Create one to get started.'}</p></Card>}
    {!isNewPage && <div className="space-y-3">{loading ? <p>Loading…</p> : visibleIntegrations.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><button type="button" className="text-left" onClick={() => navigate(`/app/integrations/email/${item.id}`)}><strong>{item.display_name || item.mailbox_email}</strong><p className="text-sm">{item.provider} · {item.mailbox_email} · {item.status}{item.is_active ? ' · Active' : ''}{item.is_fetching_stopped ? ' · Email fetching stopped' : ''}</p></button></div><div className="flex flex-wrap gap-2">{item.status !== 'CONNECTED' ? <Button onClick={async () => { try { const r = await emailIntegrationApi.reconnect(item.id); window.location.assign(r.authorization_url) } catch (e) { setError(e?.payload?.message || e?.message || 'Could not reconnect.') } }}>Reconnect</Button> : <>{!item.is_active && <Button onClick={async () => { try { await emailIntegrationApi.activate(item.id); await load() } catch (e) { setError(e?.payload?.message || e?.message || 'Could not activate mailbox.') } }}>Active</Button>}{item.is_active && item.initial_sync_configured && <Button intent="secondary" onClick={() => toggleSyncDetails(item.id)}>Sync details</Button>}{item.is_active && (item.is_fetching_stopped || !item.initial_sync_configured) && syncSetupId !== item.id && <Button disabled={syncBusy} onClick={() => startSyncSetup(item.id)}>{item.initial_sync_configured ? 'Start email fetching' : 'Schedule email fetching'}</Button>}{item.is_active && !item.is_fetching_stopped && item.initial_sync_configured && <Button disabled={syncBusy} onClick={() => changeConnection(item.id, 'pause')}>Stop email fetching</Button>}</>}{item.status !== 'DISCONNECTED' && <Button disabled={syncBusy} onClick={() => changeConnection(item.id, 'disconnect')}>Disconnect</Button>}{item.status === 'DISCONNECTED' && <button type="button" title="Delete disconnected mailbox" aria-label={`Delete ${item.mailbox_email}`} disabled={syncBusy} onClick={() => deleteIntegration(item)} className="rounded-lg border border-red-200 px-3 py-2 text-red-600 hover:bg-red-50 disabled:opacity-50">🗑</button>}</div></div>{item.is_active && syncDetailsId === item.id && <SyncDetails item={item} />}{item.status === 'CONNECTED' && item.is_active && (item.is_fetching_stopped || !item.initial_sync_configured) && syncSetupId === item.id && <form onSubmit={e => configure(e, item.id)} className="mt-4"><FetchFromEditor value={fetchFrom} onChange={setFetchFrom} boundary={fetchBoundary} /><div className="mt-4"><ScheduleEditor value={schedule} onChange={setSchedule} /></div><div className="mt-4 flex flex-wrap items-center gap-2">{item.schedule_config?.type && <Button type="button" intent="secondary" disabled={syncBusy} onClick={() => setSchedule(copySavedSchedule(item.schedule_config))}>Use last schedule</Button>}<Button type="submit" disabled={syncBusy}>Save schedule</Button><Button type="button" disabled={syncBusy} onClick={() => { setSyncSetupId(null); setError('') }}>Cancel</Button><p className="text-sm text-[var(--color-text-muted)]">Choose the fetch window first, then when this mailbox should run.</p></div></form>}{item.last_error && <p className="mt-2 text-sm text-red-600">{item.last_error}</p>}</Card>)}</div>}
    </div>
  </ClientLayout>
}

function SyncDetails({ item }) {
  const summary = item.last_sync_summary || {}
  const dateTime = (value) => formatDateTime(value, 'Not available yet')
  const [showSchedule, setShowSchedule] = useState(false)
  return <div className="mt-4 grid gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 text-sm md:grid-cols-2">
    <Detail label="Last successful mailbox check" value={dateTime(item.last_successful_sync_at)} />
    <Detail label="Next automatic mailbox check" value={item.is_fetching_stopped ? 'Schedule required' : dateTime(item.next_sync_at)} />
    <div><p className="text-xs text-[var(--color-text-muted)]">Email fetching schedule</p>{item.schedule_config?.type ? <button type="button" onClick={() => setShowSchedule(!showSchedule)} className="mt-1 text-left font-medium text-[var(--color-accent)] hover:underline">{scheduleSummary(item.schedule_config, item.sync_interval_minutes)} · {showSchedule ? 'Hide schedule' : 'View schedule'}</button> : <p className="mt-1 font-medium text-[var(--color-ink)]">{scheduleSummary(item.schedule_config, item.sync_interval_minutes)}</p>}</div>
    <Detail label="Latest processing result" value={summary.completed_at ? `${summary.emails_fetched || 0} email(s) fetched, ${summary.vendor_bill_records_created || 0} vendor-bill record(s) created, ${summary.emails_ignored || 0} ignored, ${summary.emails_deferred || 0} deferred` : 'No completed sync yet'} />
    {showSchedule && <div className="md:col-span-2"><ScheduleEditor value={copySavedSchedule(item.schedule_config)} onChange={() => {}} readOnly /></div>}
  </div>
}

function scheduleSummary(config, fallbackMinutes) {
  if (!config?.type) return `Every ${fallbackMinutes} minutes`
  const type = config.type[0] + config.type.slice(1).toLowerCase()
  const repeat = config.repeat_minutes ? ` · every ${config.repeat_minutes} minutes` : ''
  const end = config.no_end_date ? ' · no end date' : ` · ends ${config.end_date}`
  return `${type} from ${config.start_date} at ${config.start_time}${repeat}${end}`
}

function Detail({ label, value, tone }) {
  return <div><p className="text-xs text-[var(--color-text-muted)]">{label}</p><p className={tone === 'error' ? 'mt-1 font-medium text-red-600' : tone === 'success' ? 'mt-1 font-medium text-emerald-600' : 'mt-1 font-medium text-[var(--color-ink)]'}>{value}</p></div>
}

function createDefaultSchedule() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return { type: 'SINGLE', start_date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`, start_time: `${pad(now.getHours())}:${pad(now.getMinutes())}`, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Calcutta', repeat_minutes: null, repeat_every: 1, daily_mode: 'INTERVAL', weekdays: ['MONDAY'], monthly_mode: 'DAY_OF_MONTH', day_of_month: now.getDate(), week_of_month: 'FIRST', weekday: 'MONDAY', month: now.getMonth() + 1, no_end_date: true, end_date: '' }
}

function createDefaultFetchFrom(boundary = null) {
  const source = boundary ? new Date(new Date(boundary).getTime() + 60_000) : new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return {
    date: `${source.getFullYear()}-${pad(source.getMonth() + 1)}-${pad(source.getDate())}`,
    time: `${pad(source.getHours())}:${pad(source.getMinutes())}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Calcutta',
  }
}

function copySavedSchedule(savedSchedule) {
  const defaults = createDefaultSchedule()
  return { ...defaults, ...(savedSchedule || {}), weekdays: [...(savedSchedule?.weekdays || defaults.weekdays)] }
}

const fieldClass = 'rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-sm text-[var(--color-ink)]'
function FetchFromEditor({ value, onChange, boundary }) {
  const set = (key, next) => onChange({ ...value, [key]: next })
  return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4">
    <h3 className="text-base font-semibold text-[var(--color-ink)]">Fetch emails from</h3>
    <p className="mt-1 text-sm text-[var(--color-text-muted)]">Choose the first received email date and time to scan. Scheduler settings come next.</p>
    {boundary && <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">Emails through {formatDateTime(boundary)} were already fetched. Choose a later date and time.</p>}
    <div className="mt-4 grid gap-3 md:grid-cols-3"><label className="text-sm text-[var(--color-text-muted)]">Received from date<DateInput className={`${fieldClass} mt-1 block w-full pr-8`} value={value.date} onChange={e => set('date', e.target.value)} required /></label><label className="text-sm text-[var(--color-text-muted)]">Received from time<input className={`${fieldClass} mt-1 block w-full`} type="time" value={value.time} onChange={e => set('time', e.target.value)} required /></label><label className="text-sm text-[var(--color-text-muted)]">Time zone<select className={`${fieldClass} mt-1 block w-full`} value={value.timezone} onChange={e => set('timezone', e.target.value)}><option>{value.timezone}</option><option>Asia/Calcutta</option><option>UTC</option><option>America/New_York</option><option>Europe/London</option><option>Asia/Dubai</option></select></label></div>
  </div>
}

function ScheduleEditor({ value, onChange, readOnly = false }) {
  const set = (key, next) => { if (!readOnly) onChange({ ...value, [key]: next }) }
  const toggleDay = (day) => set('weekdays', value.weekdays.includes(day) ? value.weekdays.filter(item => item !== day) : [...value.weekdays, day])
  const days = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY']
  return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4">
    <h3 className="text-base font-semibold text-[var(--color-ink)]">Schedule</h3>
    <p className="mt-1 text-sm text-[var(--color-text-muted)]">{readOnly ? 'Saved schedule details. Editing is disabled.' : 'Choose when this mailbox should fetch emails, similar to a NetSuite scheduled script.'}</p>
    <fieldset disabled={readOnly} className="m-0 min-w-0 border-0 p-0">
    <div className="mt-4 flex flex-wrap gap-3">{['SINGLE', 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'].map(type => <label key={type} className="flex items-center gap-2 text-sm text-[var(--color-ink)]"><input type="radio" name="schedule-type" checked={value.type === type} onChange={() => set('type', type)} />{type[0] + type.slice(1).toLowerCase()} event</label>)}</div>
    <div className="mt-4 grid gap-3 md:grid-cols-3"><label className="text-sm text-[var(--color-text-muted)]">Start date<DateInput className={`${fieldClass} mt-1 block w-full pr-8`} value={value.start_date} onChange={e => set('start_date', e.target.value)} required /></label><label className="text-sm text-[var(--color-text-muted)]">Start time<input className={`${fieldClass} mt-1 block w-full`} type="time" value={value.start_time} onChange={e => set('start_time', e.target.value)} required /></label><label className="text-sm text-[var(--color-text-muted)]">Time zone<select className={`${fieldClass} mt-1 block w-full`} value={value.timezone} onChange={e => set('timezone', e.target.value)}><option>{value.timezone}</option><option>Asia/Calcutta</option><option>UTC</option><option>America/New_York</option><option>Europe/London</option><option>Asia/Dubai</option></select></label></div>
    {value.type === 'DAILY' && <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><label><input type="radio" checked={value.daily_mode === 'INTERVAL'} onChange={() => set('daily_mode', 'INTERVAL')} /> Every</label><input className={`${fieldClass} w-20`} type="number" min="1" disabled={value.daily_mode !== 'INTERVAL'} value={value.repeat_every} onChange={e => set('repeat_every', Number(e.target.value))} /><span>day(s)</span><label><input type="radio" checked={value.daily_mode === 'WEEKDAYS'} onChange={() => set('daily_mode', 'WEEKDAYS')} /> Selected weekdays</label></div>}
    {(value.type === 'DAILY' && value.daily_mode === 'WEEKDAYS' || value.type === 'WEEKLY') && <div className="mt-3"><div className="flex flex-wrap gap-3">{days.map(day => <label key={day} className="text-xs"><input type="checkbox" checked={value.weekdays.includes(day)} onChange={() => toggleDay(day)} /> {day.slice(0, 3)}</label>)}</div><p className="mt-1 text-xs text-[var(--color-text-muted)]">Email fetching will run only on the selected days.</p></div>}
    {(value.type === 'WEEKLY') && <label className="mt-4 flex items-center gap-2 text-sm">Repeat every <input className={`${fieldClass} w-20`} type="number" min="1" value={value.repeat_every} onChange={e => set('repeat_every', Number(e.target.value))} /> week(s)</label>}
    {(value.type === 'MONTHLY' || value.type === 'YEARLY') && <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><select className={fieldClass} value={value.monthly_mode} onChange={e => set('monthly_mode', e.target.value)}><option value="DAY_OF_MONTH">Day of month</option><option value="DAY_OF_WEEK">Nth weekday</option></select>{value.monthly_mode === 'DAY_OF_MONTH' ? <label>Day <input className={`${fieldClass} ml-1 w-20`} type="number" min="1" max="31" value={value.day_of_month} onChange={e => set('day_of_month', Number(e.target.value))} /></label> : <><select className={fieldClass} value={value.week_of_month} onChange={e => set('week_of_month', e.target.value)}>{['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'LAST'].map(item => <option key={item}>{item}</option>)}</select><select className={fieldClass} value={value.weekday} onChange={e => set('weekday', e.target.value)}>{days.map(item => <option key={item}>{item}</option>)}</select></>}{value.type === 'YEARLY' && <label>of month <select className={`${fieldClass} ml-1`} value={value.month} onChange={e => set('month', Number(e.target.value))}>{Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{new Date(2000, i, 1).toLocaleString(undefined, { month: 'long' })}</option>)}</select></label>}</div>}
    {value.type !== 'SINGLE' && <label className="mt-4 flex flex-wrap items-center gap-2 text-sm text-[var(--color-ink)]">Repeat <select className={fieldClass} value={value.repeat_minutes || ''} onChange={e => set('repeat_minutes', e.target.value ? Number(e.target.value) : null)}><option value="">At scheduled time</option><option value="15">Every 15 minutes</option><option value="30">Every 30 minutes</option><option value="60">Every hour</option><option value="120">Every 2 hours</option><option value="240">Every 4 hours</option><option value="360">Every 6 hours</option><option value="720">Every 12 hours</option></select></label>}
    {value.type !== 'SINGLE' && <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><label className="flex items-center gap-2"><input type="checkbox" checked={value.no_end_date} onChange={e => onChange({ ...value, no_end_date: e.target.checked, end_date: e.target.checked ? '' : value.end_date })} /> No end date</label>{!value.no_end_date && <label>End by <DateInput className={`${fieldClass} ml-2 pr-8`} value={value.end_date} onChange={e => set('end_date', e.target.value)} required /></label>}</div>}
    </fieldset>
  </div>
}

