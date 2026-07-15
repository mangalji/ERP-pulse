import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [localError, setLocalError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLocalError('')
    if (password !== confirmPassword) {
      setLocalError('Passwords do not match')
      return
    }
    setIsSubmitting(true)
    try {
      const result = await register(email, password, confirmPassword)
      navigate('/otp-verification', { state: { purpose: 'registration', email: result.email } })
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Failed to send OTP')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Get started"
      title="Create your account"
      subtitle="We'll send a verification code to your email."
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
        <Input
          id="password"
          type="password"
          label="Password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          id="confirmPassword"
          type="password"
          label="Confirm password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
        {localError && <p className="text-center text-sm text-[var(--color-negative)]">{localError}</p>}
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-[var(--color-primary)]">
          Log in
        </Link>
      </p>
    </AuthLayout>
  )
}
