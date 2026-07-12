import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    setTimeout(() => {
      setIsSubmitting(false)
      navigate('/otp-verification', { state: { purpose: 'registration' } })
    }, 700)
  }

  return (
    <AuthLayout
      eyebrow="Get started"
      title="Create your account"
      subtitle="We'll send a verification code to your email."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <Input id="firstName" label="First name" placeholder="Jane" required />
          <Input id="lastName" label="Last name" placeholder="Doe" required />
        </div>
        <Input id="email" type="email" label="Email" placeholder="you@company.com" required />
        <Input id="mobile" type="tel" label="Mobile number" placeholder="+1 555 123 4567" required />
        <Input id="password" type="password" label="Password" placeholder="••••••••" required />
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
