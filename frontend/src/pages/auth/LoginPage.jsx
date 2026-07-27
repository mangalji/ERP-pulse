import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [localError, setLocalError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLocalError('')
    setIsSubmitting(true)
    try {
      const result = await login(email, password)
      navigate('/otp-verification', { state: { purpose: 'login', email: result.email } })
    } catch (err) {
      setLocalError(err.payload?.message || err.message || 'Failed to send OTP')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout eyebrow="Welcome back" title="Log in to ERP Pulse" subtitle="Enter your email and password to continue.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="email"
          type="email"
          label="Email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          error={localError}
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
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Continue
        </Button>
      </form>
      <div className="mt-4 flex flex-col items-center gap-2">
        <Link
          to="/forgot-password"
          className="text-sm font-medium text-[var(--color-primary)] hover:underline"
        >
          Forgot password?
        </Link>
      </div>
      <p className="mt-4 text-center text-sm text-[var(--color-muted)]">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="font-medium text-[var(--color-primary)]">
          Register
        </Link>
      </p>
    </AuthLayout>
  )
}
