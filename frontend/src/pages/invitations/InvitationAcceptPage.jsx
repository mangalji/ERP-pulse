import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import InvitationCard from '../../components/invitations/InvitationCard.jsx'
import PasswordSetupForm from '../../components/invitations/PasswordSetupForm.jsx'
import InvitationExpired from '../../components/invitations/InvitationExpired.jsx'
import InvitationSuccess from '../../components/invitations/InvitationSuccess.jsx'
import { invitationApi } from '../../services/invitations.js'

export default function InvitationAcceptPage() {
  const { token } = useParams()
  const { toasts, addToast, removeToast } = useToast()

  const [status, setStatus] = useState('loading')
  const [invitation, setInvitation] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

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

  const handleAccept = async ({ password, confirm_password, first_name, last_name }) => {
    setIsSubmitting(true)
    setError('')
    try {
      await invitationApi.accept({
        token,
        password,
        confirm_password,
        first_name,
        last_name,
      })
      setStatus('success')
      addToast('Account created successfully!', 'success')
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to accept invitation.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResend = async () => {
    try {
      await invitationApi.publicResend(invitation?.email)
      addToast('Invitation resent successfully.', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to resend invitation.', 'error')
    }
  }

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <p className="text-sm text-[var(--color-muted)]">Loading invitation...</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <InvitationSuccess />
        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    )
  }

  if (status === 'expired' || invitation?.status !== 'PENDING') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)]">
        <InvitationExpired onResend={invitation ? handleResend : undefined} />
        <Toast toasts={toasts} removeToast={removeToast} />
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
          onResend={handleResend}
        />
        <div className="mt-6">
          <h2 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            Set up your account
          </h2>
          <PasswordSetupForm onSubmit={handleAccept} isLoading={isSubmitting} />
          {error && <p className="mt-2 text-sm text-[var(--color-negative)]">{error}</p>}
        </div>
        <p className="mt-4 text-center text-xs text-[var(--color-muted)]">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-[var(--color-primary)] hover:underline">
            Log in
          </Link>
        </p>
      </div>
      <Toast toasts={toasts} removeToast={removeToast} />
    </div>
  )
}
