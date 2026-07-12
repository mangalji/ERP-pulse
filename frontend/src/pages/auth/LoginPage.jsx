import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'

export default function LoginPage() {
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    // UI-only: no API call yet. Simulates the request → OTP-sent transition.
    setTimeout(() => {
      setIsSubmitting(false)
      navigate('/otp-verification', { state: { purpose: 'login' } })
    }, 700)
  }

  return (
    <AuthLayout eyebrow="Welcome back" title="Log in to ERP Pulse" subtitle="Enter your email and password to continue.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input id="email" type="email" label="Email" placeholder="you@company.com" required />
        <Input id="password" type="password" label="Password" placeholder="••••••••" required />
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Continue
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="font-medium text-[var(--color-primary)]">
          Register
        </Link>
      </p>
    </AuthLayout>
  )
}
