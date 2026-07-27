import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import OtpInput from '../../components/ui/OtpInput.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { resetPassword } = useAuth()
  const email = location.state?.email ?? ''
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setIsSubmitting(true)
    try {
      await resetPassword(email, code, password, confirmPassword)
      navigate('/login', {
        state: { resetSuccess: true },
        replace: true,
      })
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to reset password')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Reset password"
      title="Enter reset code & new password"
      subtitle="Enter the code sent to your email and choose a new password."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <OtpInput value={code} onChange={setCode} />

        <Input
          id="password"
          type="password"
          label="New password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          id="confirmPassword"
          type="password"
          label="Confirm new password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />

        {error && <p className="text-center text-sm text-[var(--color-negative)]">{error}</p>}

        <Button type="submit" isLoading={isSubmitting} disabled={code.length < 6} className="mt-2 w-full">
          Reset password
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
        Remember your password?{' '}
        <Link to="/login" className="font-medium text-[var(--color-primary)]">
          Log in
        </Link>
      </p>
    </AuthLayout>
  )
}
