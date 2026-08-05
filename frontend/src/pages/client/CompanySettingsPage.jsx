import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { clientApi } from '../../services/client.js'

/**
 * Company Settings — loads and updates the current company's profile
 * via the company-scoped /client/settings/ endpoint. The backend pins
 * the company to the authenticated user, so no company_id is sent.
 */
export default function CompanySettingsPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    contact_email: '',
    contact_phone: '',
    country: '',
    timezone: '',
    currency: '',
    language: '',
    date_format: '',
    number_format: '',
  })

  const loadSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await clientApi.getCompanySettings()
      setSettings(data)
      setForm({
        contact_email: data.contact_email || '',
        contact_phone: data.contact_phone || '',
        country: data.country || '',
        timezone: data.timezone || '',
        currency: data.currency || '',
        language: data.language || '',
        date_format: data.date_format || '',
        number_format: data.number_format || '',
      })
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load company settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleChange = (field) => (event) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const handleSave = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = {}
      if (form.contact_email !== settings?.contact_email) payload.contact_email = form.contact_email
      if (form.contact_phone !== settings?.contact_phone) payload.contact_phone = form.contact_phone
      if (form.country !== settings?.country) payload.country = form.country
      if (form.timezone !== settings?.timezone) payload.timezone = form.timezone
      if (form.currency !== settings?.currency) payload.currency = form.currency
      if (form.language !== settings?.language) payload.language = form.language
      if (form.date_format !== settings?.date_format) payload.date_format = form.date_format
      if (form.number_format !== settings?.number_format) payload.number_format = form.number_format

      if (Object.keys(payload).length > 0) {
        const updated = await clientApi.updateCompanySettings(payload)
        setSettings(updated)
      }
      addToast('Company settings saved', 'success')
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to save company settings')
      addToast('Failed to save company settings', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ClientLayout title="Company Settings" breadcrumb="Company Settings">
      <div className="max-w-2xl flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Company Settings
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Manage your company's profile and preferences.
            </p>
          </div>
          <Badge tone="primary">Company Admin</Badge>
        </div>

        {loading ? (
          <Card className="p-6">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="mt-4 h-8 w-full" />
            <Skeleton className="mt-4 h-8 w-full" />
          </Card>
        ) : error && !settings ? (
          <Card className="p-6">
            <ErrorState message={error} onRetry={loadSettings} />
          </Card>
        ) : (
          <>
            <Card className="p-6">
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Company Profile
              </h2>
              <form onSubmit={handleSave} className="flex flex-col gap-4">
                <Input id="csName" label="Company name" value={settings?.name || '—'} readOnly />
                <Input id="csCode" label="Company code" value={settings?.code || '—'} readOnly />
                <Input
                  id="csEmail"
                  label="Contact email"
                  value={form.contact_email}
                  onChange={handleChange('contact_email')}
                />
                <Input
                  id="csPhone"
                  label="Contact phone"
                  value={form.contact_phone}
                  onChange={handleChange('contact_phone')}
                />
                <Input
                  id="csCountry"
                  label="Country"
                  value={form.country}
                  onChange={handleChange('country')}
                />
                {error && <p className="text-sm text-[var(--color-negative)]">{error}</p>}
                <Button type="submit" isLoading={saving} className="w-fit">
                  Save changes
                </Button>
              </form>
            </Card>

            <Card className="p-6">
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Preferences
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input id="csTimezone" label="Timezone" value={form.timezone} onChange={handleChange('timezone')} />
                <Input id="csCurrency" label="Currency" value={form.currency} onChange={handleChange('currency')} />
                <Input id="csLanguage" label="Language" value={form.language} onChange={handleChange('language')} />
                <Input id="csDateFormat" label="Date format" value={form.date_format} onChange={handleChange('date_format')} />
                <Input id="csNumFormat" label="Number format" value={form.number_format} onChange={handleChange('number_format')} />
              </div>
            </Card>
          </>
        )}
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </ClientLayout>
  )
}
