import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Button from '../components/ui/Button.jsx'
import OtpInput from '../components/ui/OtpInput.jsx'
import Badge from '../components/ui/Badge.jsx'
import Toast, { useToast } from '../components/ui/Toast.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function SettingsPage() {
  const { user, updateProfile, netSuiteConnected, connectNetSuite } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const { toasts, addToast, removeToast } = useToast()

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [profilePic, setProfilePic] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [step, setStep] = useState('form')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [otpLoading, setOtpLoading] = useState(false)
  const [localError, setLocalError] = useState('')
  const [otpSuccess, setOtpSuccess] = useState('')
  const [otpSent, setOtpSent] = useState(false)

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '')
      setLastName(user.last_name || '')
      setMobileNumber(user.mobile_number || '')
      setProfilePic(user.profile_pic || '')
    }
  }, [user])

  useEffect(() => {
    if (searchParams.get('netsuite') === 'connected') {
      connectNetSuite()
      addToast('NetSuite account connected successfully', 'success')
      searchParams.delete('netsuite')
      setSearchParams(searchParams, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const handleSendOtp = async () => {
    setLocalError('')
    setOtpSuccess('')
    setOtpLoading(true)
    try {
      await updateProfile()
      setOtpSent(true)
      setStep('otp')
      addToast('Verification code sent to your email', 'success')
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Failed to send verification code')
    } finally {
      setOtpLoading(false)
    }
  }

  const handleVerifyOtp = async (event) => {
    event.preventDefault()
    setLocalError('')
    setOtpSuccess('')
    setIsSubmitting(true)
    try {
      await updateProfile(otpCode, { firstName, lastName, mobileNumber, profilePic })
      setOtpSuccess('Profile updated successfully.')
      setStep('form')
      setOtpSent(false)
      setOtpCode('')
      addToast('Profile updated successfully', 'success')
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Failed to update profile')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleFormSubmit = (event) => {
    event.preventDefault()
    setLocalError('')
    if (!otpSent) {
      handleSendOtp()
    }
  }

  return (
    <DashboardLayout title="Settings">
      <div className="flex max-w-xl flex-col gap-6">
        <Card className="p-6">
          <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            Profile
          </h2>
          <form onSubmit={handleFormSubmit} className="mt-4 flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Input
                id="settingsFirstName"
                label="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
              <Input
                id="settingsLastName"
                label="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <Input id="settingsEmail" type="email" label="Email" defaultValue={user?.email || ''} disabled />
            <Input
              id="settingsMobile"
              type="tel"
              label="Mobile number"
              value={mobileNumber}
              onChange={(e) => setMobileNumber(e.target.value)}
              placeholder="+1 555 123 4567"
            />
            <Input
              id="settingsProfilePic"
              type="url"
              label="Profile picture URL"
              value={profilePic}
              onChange={(e) => setProfilePic(e.target.value)}
              placeholder="https://example.com/photo.jpg"
            />
            {localError && <p className="text-sm text-[var(--color-negative)]">{localError}</p>}
            {otpSuccess && <p className="text-sm text-[var(--color-positive)]">{otpSuccess}</p>}
            <Button type="submit" isLoading={isSubmitting || otpLoading} className="w-fit">
              {otpSent ? 'Verify & Save' : 'Save changes'}
            </Button>
          </form>
        </Card>

        {step === 'otp' && (
          <Card className="p-6">
            <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Verify Profile Update
            </h2>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Enter the verification code sent to your email.
            </p>
            <form onSubmit={handleVerifyOtp} className="mt-4 flex flex-col gap-4">
              <OtpInput value={otpCode} onChange={setOtpCode} />
              {localError && <p className="text-sm text-[var(--color-negative)]">{localError}</p>}
              <Button type="submit" isLoading={isSubmitting} disabled={otpCode.length < 6} className="w-fit">
                Verify & Update Profile
              </Button>
            </form>
          </Card>
        )}

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              NetSuite Connection
            </h2>
            <Badge tone={netSuiteConnected ? 'positive' : 'netsuite'}>
              {netSuiteConnected ? 'Connected' : 'Not connected'}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-[var(--color-muted)]">
            Connect additional accounts, switch the active one, or remove a connection.
          </p>
          <Link
            to="/connect-netsuite"
            className="mt-3 inline-block text-sm font-medium text-[var(--color-primary)] hover:underline"
          >
            Manage NetSuite connections &rarr;
          </Link>
        </Card>
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </DashboardLayout>
  )
}
