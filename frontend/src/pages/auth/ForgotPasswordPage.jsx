import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function ForgotPasswordPage() {
  const { forgotPassword } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setSuccess('')
    setIsSubmitting(true)
    try {
      const result = await forgotPassword(email)
      const msg = result.message || 'If this email is registered, a password reset code has been sent to it.'
      setSuccess(msg)
      // Auto-redirect to reset code page after a short delay
      setTimeout(() => {
        navigate('/reset-password', { state: { email } })
      }, 1500)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to send reset code')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Reset password"
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a code to reset it."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="email"
          type="email"
          label="Email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        {error && <p className="text-center text-sm text-[var(--color-negative)]">{error}</p>}
        {success && <p className="text-center text-sm text-[var(--color-positive)]">{success}</p>}
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Send reset code
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
        Remember your password?{' '}
        <Link to="/login" className="font-medium text-[var(--color-primary)]">
          Log in
        </Link>
      </p>
      {success && (
        <div className="mt-4 text-center">
          <p className="text-xs text-[var(--color-muted)]">
            Redirecting to enter your code...
          </p>
          <Link
            to="/reset-password"
            state={{ email }}
            className="text-sm font-medium text-[var(--color-primary)]"
          >
            Enter reset code
          </Link>
        </div>
      )}
    </AuthLayout>
  )
}
