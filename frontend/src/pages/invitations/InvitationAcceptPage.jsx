import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import InvitationCard from '../../components/invitations/InvitationCard.jsx'
import PasswordSetupForm from '../../components/invitations/PasswordSetupForm.jsx'
import InvitationExpired from '../../components/invitations/InvitationExpired.jsx'
import InvitationSuccess from '../../components/invitations/InvitationSuccess.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { invitationApi } from '../../services/invitations.js'

export default function InvitationAcceptPage() {
  const { token } = useParams()
  const { toasts, addToast, removeToast } = useToast()

  const [status, setStatus] = useState('loading')
  const [invitation, setInvitation] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setError('Invalid invitation link.')
      return
    }

    invitationApi
      .validate(token)
      .then((data) => {
        setInvitation(data)
        setStatus('valid')
      })
      .catch((err) => {
        setError(err.payload?.message || err.message || 'Invalid invitation.')
        setStatus('expired')
      })
  }, [token])

  const handleRequestOtp = async ({password: submittedPassword,confirm_password, mobile_number}) =>{
    setIsSubmitting(true)
    setError('')
    try{
      await invitationApi.requestOtp({token, password: submittedPassword, confirm_password})
      setPassword(submittedPassword)
      setMobileNumber(mobile_number || '')
      setStatus('otp')
      addToast(
        'OTP sent successfully. Please check your email.',
        'success'
      )
    }
    catch (err){
      setError(
        err.payload?.message || err.message || 'Failed to send OTP.'
      )
      }
     finally {
      setIsSubmitting(false)
    }
  }
  const handleVerifyOtp = async (e) => {
    e.preventDefault()

    setError('')

    if (!otp || otp.length !== 6) {
      setError('Please enter the 6-digit OTP.')
      return
    }

    setIsSubmitting(true)
     try {
      await invitationApi.accept({
        token,
        password,
        otp,
        mobile_number: mobileNumber,
      })
      setStatus('success')
      addToast(
        'Account created successfully!',
        'success'
      )
    } catch (err){
      setError(
        err.payload?.message ||
        err.message ||
        'Invalid OTP or failed to activate account.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <p className="text-sm text-[var(--color-muted)]">
          Loading invitation...
        </p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <InvitationSuccess />
        <Toast
          toasts={toasts}
          removeToast={removeToast}
        />
      </div>
    )
  }

  if (status === 'expired' || invitation?.status !== 'PENDING') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <div className="w-full max-w-md"></div>
        <InvitationExpired />
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}
        <div className="mt-4 text-center">
          <p className="text-xs text-[var(--color-muted)]">
            Please contact your administrator to request a new invitation.
          </p>

          <Link
            to="/login"
            className="mt-2 inline-block text-sm font-medium text-[var(--color-primary)] hover:underline"
          >
            Back to login
          </Link>
        </div>
        <Toast
          toasts={toasts}
          removeToast={removeToast}
        />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)] p-4">
      <div className="w-full max-w-md">
        <InvitationCard
          companyName={invitation?.company_name}
          email={invitation?.email}
          expiresAt={invitation?.expires_at}
        />

        <div className="mt-6">
          {status === 'valid' && (
            <>
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Set up your account
              </h2>

              <PasswordSetupForm
                onSubmit={handleRequestOtp}
                isLoading={isSubmitting}
              />
            </>
          )}

          {status === 'otp' && (
            <>
              <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                Verify your email
              </h2>

              <p className="mb-4 text-sm text-[var(--color-muted)]">
                We sent a 6-digit OTP to{' '}
                <strong>{invitation?.email}</strong>.
                Enter it below to activate your account.
              </p>

              <form
                onSubmit={handleVerifyOtp}
                className="flex flex-col gap-4"
              >
                <Input
                  label="OTP"
                  type="text"
                  value={otp}
                  onChange={(e) =>
                    setOtp(
                      e.target.value
                        .replace(/\D/g, '')
                        .slice(0, 6)
                    )
                  }
                  inputMode="numeric"
                  maxLength={6}
                  required
                />

                {error && (
                  <p className="text-sm text-[var(--color-negative)]">
                    {error}
                  </p>
                )}

                <Button
                  type="submit"
                  isLoading={isSubmitting}
                  className="w-full"
                >
                  Verify OTP & Activate Account
                </Button>
              </form>
            </>
          )}

          {status !== 'otp' && error && (
            <p className="mt-2 text-sm text-[var(--color-negative)]">
              {error}
            </p>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-[var(--color-muted)]">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-[var(--color-primary)] hover:underline"
          >
            Log in
          </Link>
        </p>
      </div>

      <Toast
        toasts={toasts}
        removeToast={removeToast}
      />
    </div>
  )
}