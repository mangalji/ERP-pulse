import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import OtpInput from '../../components/ui/OtpInput.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function ProfilePage() {
  const { user, profileSendOtp, profileUpdate } = useAuth()
  const { toasts, addToast, removeToast } = useToast()

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [profilePic, setProfilePic] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [step, setStep] = useState('form')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [otpLoading, setOtpLoading] = useState(false)
  const [otpSent, setOtpSent] = useState(false)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '')
      setLastName(user.last_name || '')
      setMobileNumber(user.mobile_number || '')
      setProfilePic(user.profile_pic || '')
    }
  }, [user])

  const handleSendOtp = async () => {
    setLocalError('')
    setOtpLoading(true)
    try {
      await profileSendOtp()
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
    setIsSubmitting(true)
    try {
      await profileUpdate(otpCode, { firstName, lastName, mobileNumber, profilePic })
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
    if (!otpSent) handleSendOtp()
  }

  return (
    <ClientLayout title="Profile" breadcrumb="Profile">
      <div className="flex max-w-xl flex-col gap-6">
        <div>
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Your Profile
          </h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            Update your personal details. Changes require email verification.
          </p>
        </div>

        <Card className="p-6">
          <form onSubmit={handleFormSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Input
                id="profileFirst"
                label="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
              <Input
                id="profileLast"
                label="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <Input id="profileEmail" type="email" label="Email" value={user?.email || ''} readOnly />
            <Input
              id="profileMobile"
              type="tel"
              label="Mobile number"
              value={mobileNumber}
              onChange={(e) => setMobileNumber(e.target.value)}
            />
            <Input
              id="profilePic"
              type="url"
              label="Profile picture URL"
              value={profilePic}
              onChange={(e) => setProfilePic(e.target.value)}
            />
            {localError && <p className="text-sm text-[var(--color-negative)]">{localError}</p>}
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
                Verify & Update
              </Button>
            </form>
          </Card>
        )}
      </div>

      <Toast toasts={toasts} removeToast={removeToast} />
    </ClientLayout>
  )
}
