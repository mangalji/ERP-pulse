import { useEffect, useState } from 'react'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function SettingsPage() {
  const { user, profileUpdate } = useAuth()
  const [form, setForm] = useState({ firstName: '', lastName: '', mobileNumber: '' })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setForm({
      firstName: user?.first_name || '',
      lastName: user?.last_name || '',
      mobileNumber: user?.mobile_number || '',
    })
  }, [user])

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    setError('')

    try {
      await profileUpdate(form)
      setMessage('Profile updated successfully.')
    } catch (requestError) {
      const details = requestError.payload?.data || requestError.payload
      const firstError = details && typeof details === 'object'
        ? Object.values(details).flat().find(Boolean)
        : null
      setError(firstError || requestError.message || 'Unable to update profile.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AdminLayout title="Settings" breadcrumb="Settings">
      <div className="flex flex-col gap-6">
        <PageHeader title="Settings" subtitle="Manage your AGSuite super admin preferences." />

        <SectionCard title="Profile" subtitle="Update your contact details.">
          <form className="flex max-w-2xl flex-col gap-4" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                id="profile-first-name"
                label="First Name"
                value={form.firstName}
                onChange={updateField('firstName')}
                required
                maxLength={100}
              />
              <Input
                id="profile-last-name"
                label="Last Name"
                value={form.lastName}
                onChange={updateField('lastName')}
                required
                maxLength={100}
              />
            </div>
            <Input
              id="profile-mobile-number"
              label="Mobile Number"
              type="tel"
              value={form.mobileNumber}
              onChange={updateField('mobileNumber')}
              placeholder="+919876543210"
              maxLength={16}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                id="profile-email"
                label="Email"
                value={user?.email || ''}
                disabled
              />
              <Input
                id="profile-role"
                label="Role"
                value="Super Admin"
                disabled
              />
            </div>
            {error && <p className="text-sm text-[var(--color-negative)]">{error}</p>}
            {message && <p className="text-sm text-[var(--color-success)]">{message}</p>}
            <div>
              <Button type="submit" isLoading={saving}>Save Profile</Button>
            </div>
          </form>
        </SectionCard>
      </div>
    </AdminLayout>
  )
}
