import { useState, useCallback } from 'react'
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
  const email = location.state?.email ?? ''
  const [code, setCode] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [localError, setLocalError] = useState('')
  const [resendLoading, setResendLoading] = useState(false)
  const [resendSuccess, setResendSuccess] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLocalError('')
    setResendSuccess('')
    setIsSubmitting(true)
    try {
      if (purpose === 'login') {
        await verifyLogin(email, code)
        navigate('/dashboard', { replace: true })
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

  return (
    <AuthLayout
      eyebrow="Verify your email"
      title="Enter verification code"
      subtitle={`We sent a 6-digit code to your email to confirm your ${
        purpose === 'registration' ? 'registration' : 'login'
      }.`}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
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
