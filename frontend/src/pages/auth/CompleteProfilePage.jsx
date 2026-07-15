import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import AuthLayout from '../../components/layout/AuthLayout.jsx'
import Input from '../../components/ui/Input.jsx'
import Button from '../../components/ui/Button.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function CompleteProfilePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { completeProfile } = useAuth()
  const registrationToken = location.state?.registrationToken
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (!registrationToken) {
    navigate('/register', { replace: true })
    return null
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await completeProfile(registrationToken, firstName, lastName, mobileNumber)
      navigate('/login', { replace: true })
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to complete profile')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      eyebrow="Almost there"
      title="Complete your profile"
      subtitle="Tell us a bit more about yourself to finish registration."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <Input
            id="firstName"
            label="First name"
            placeholder="Jane"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />
          <Input
            id="lastName"
            label="Last name"
            placeholder="Doe"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />
        </div>
        <Input
          id="mobileNumber"
          type="tel"
          label="Mobile number"
          placeholder="+1 555 123 4567"
          value={mobileNumber}
          onChange={(e) => setMobileNumber(e.target.value)}
          required
        />
        {error && <p className="text-center text-sm text-[var(--color-negative)]">{error}</p>}
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Finish registration
        </Button>
      </form>
    </AuthLayout>
  )
}
