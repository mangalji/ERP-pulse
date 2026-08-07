import { useState, useCallback, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import OtpInput from '../../components/ui/OtpInput.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function OtpVerificationPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { verifyLogin, verifyRegister, resendLoginOtp, resendRegisterOtp, error } = useAuth()
  const purpose = location.state?.purpose ?? 'login'
  const emailFromState = location.state?.email ?? ''
  const [email, setEmail] = useState(emailFromState)
  const [code, setCode] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [localError, setLocalError] = useState('')
  const [resendLoading, setResendLoading] = useState(false)
  const [resendSuccess, setResendSuccess] = useState('')
  const [editEmail, setEditEmail] = useState(false)
  const [tempEmail, setTempEmail] = useState(email)
  const [secondsRemaining, setSecondsRemaining] = useState(300)

  useEffect(() => {
    if (!emailFromState) {
      navigate(`/${purpose === 'login' ? 'login' : 'register'}`, { replace: true })
    }
    if (purpose === 'password-reset') {
      navigate('/reset-password', { replace: true })
    }
  }, [emailFromState, purpose, navigate])

  useEffect(() => {
    if (secondsRemaining <= 0) {
      navigate(`/${purpose === 'login' ? 'login' : 'register'}`, { replace: true })
      return
    }
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [secondsRemaining, purpose, navigate])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLocalError('')
    setResendSuccess('')
    setIsSubmitting(true)
    try {
      if (purpose === 'login') {
        const userData = await verifyLogin(email, code)
        const isSuperAdmin = Boolean(userData?.is_superadmin || userData?.is_staff)
        navigate(isSuperAdmin ? '/admin' : '/app', { replace: true })
      } else {
        const result = await verifyRegister(email, code)
        navigate('/complete-profile', { state: { registrationToken: result.registration_token, email } })
      }
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Invalid OTP')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResend = useCallback(async () => {
    setResendSuccess('')
    setLocalError('')
    setResendLoading(true)
    try {
      if (purpose === 'login') {
        await resendLoginOtp(email)
      } else {
        await resendRegisterOtp(email)
      }
      setResendSuccess('A new code has been sent to your email.')
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Failed to resend code')
    } finally {
      setResendLoading(false)
    }
  }, [purpose, email, resendLoginOtp, resendRegisterOtp])

  const handleEditEmail = () => {
    setTempEmail(email)
    setEditEmail(true)
  }

  const handleSaveEmail = () => {
    const trimmed = tempEmail.trim()
    if (!trimmed) return
    setEmail(trimmed)
    setEditEmail(false)
  }

  const minutes = Math.floor(secondsRemaining / 60)
  const seconds = secondsRemaining % 60

  return (
    <AuthLayout
      eyebrow="Verify your email"
      title="Enter verification code"
      subtitle={`We sent a 6-digit code to your email to confirm your ${
        purpose === 'registration' ? 'registration' : 'login'
      }.`}
    >
      <div className="flex items-center justify-between rounded-lg bg-[var(--color-surface-soft)] px-4 py-3">
        {editEmail ? (
          <>
            <input
              type="email"
              value={tempEmail}
              onChange={(e) => setTempEmail(e.target.value)}
              className="flex-1 rounded border border-[var(--color-border)] bg-transparent px-2 py-1 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]"
              autoFocus
            />
            <button
              type="button"
              onClick={handleSaveEmail}
              className="ml-2 text-sm font-medium text-[var(--color-primary)] hover:underline"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditEmail(false)}
              className="ml-2 text-sm font-medium text-[var(--color-muted)] hover:underline"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <span className="text-sm font-medium text-[var(--color-ink)]">
              {email}
            </span>
            <button
              type="button"
              onClick={handleEditEmail}
              className="text-sm font-medium text-[var(--color-primary)] hover:underline"
            >
              Edit
            </button>
          </>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-[var(--color-muted)]">Code expires in</span>
        <span className={`font-medium ${secondsRemaining <= 60 ? 'text-[var(--color-negative)]' : 'text-[var(--color-ink)]'}`}>
          {minutes}:{seconds.toString().padStart(2, '0')}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-6">
        <OtpInput value={code} onChange={setCode} />
        {(localError || error) && <p className="text-center text-sm text-[var(--color-negative)]">{localError || error}</p>}
        {resendSuccess && <p className="text-center text-sm text-[var(--color-positive)]">{resendSuccess}</p>}
        <Button type="submit" isLoading={isSubmitting} disabled={code.length < 6} className="w-full">
          Verify
        </Button>
      </form>
      <button
        type="button"
        onClick={handleResend}
        disabled={resendLoading}
        className="mt-6 w-full text-center text-sm font-medium text-[var(--color-primary)] disabled:opacity-50"
      >
        {resendLoading ? 'Sending...' : 'Resend code'}
      </button>
    </AuthLayout>
  )
}
