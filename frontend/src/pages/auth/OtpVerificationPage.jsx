import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import OtpInput from '../../components/ui/OtpInput.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function OtpVerificationPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const purpose = location.state?.purpose ?? 'login'
  const [code, setCode] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    setTimeout(() => {
      setIsSubmitting(false)
      login()
      navigate('/dashboard')
    }, 700)
  }

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
        <Button type="submit" isLoading={isSubmitting} disabled={code.length < 6} className="w-full">
          Verify
        </Button>
      </form>
      <button className="mt-6 w-full text-center text-sm font-medium text-[var(--color-primary)]">
        Resend code
      </button>
    </AuthLayout>
  )
}
