import { useMemo, useState } from 'react'
import Input from '../ui/Input.jsx'
import Button from '../ui/Button.jsx'

const PASSWORD_MIN_LENGTH = 8
const PASSWORD_MAX_LENGTH = 128

const passwordRules = [
  {
    key: 'length',
    label: `At least ${PASSWORD_MIN_LENGTH} characters`,
    test: (value) => value.length >= PASSWORD_MIN_LENGTH,
  },
  {
    key: 'uppercase',
    label: 'At least one uppercase letter',
    test: (value) => /[A-Z]/.test(value),
  },
  {
    key: 'lowercase',
    label: 'At least one lowercase letter',
    test: (value) => /[a-z]/.test(value),
  },
  {
    key: 'number',
    label: 'At least one number',
    test: (value) => /\d/.test(value),
  },
  {
    key: 'special',
    label: 'At least one special character',
    test: (value) => /[^A-Za-z0-9]/.test(value),
  },
]

export default function PasswordSetupForm({ onSubmit, isLoading }) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [mobileNumber, setMobileNumber] = useState('')
  const [mobileTouched, setMobileTouched] = useState(false)

  const passwordValidation = useMemo(
    () =>
      passwordRules.reduce((result, rule) => {
        result[rule.key] = rule.test(password)
        return result
      }, {}),
    [password],
  )

  const passwordValid = passwordRules.every(
    (rule) => passwordValidation[rule.key],
  )

  const confirmPasswordValid =
    confirmPassword.length > 0 && password === confirmPassword

  const mobileDigits = mobileNumber.replace(/\D/g, '')
  const mobileValid = mobileDigits.length >= 7 && mobileDigits.length <= 15

  const formValid =
    passwordValid &&
    confirmPasswordValid &&
    mobileDigits.length > 0 &&
    mobileValid

  const handlePasswordChange = (value) => {
    setPassword(value)
  }

  const handleConfirmPasswordChange = (value) => {
    setConfirmPassword(value)
  }

  const handleMobileChange = (value) => {
    const digitsOnly = value.replace(/\D/g, '').slice(0, 15)
    setMobileNumber(digitsOnly)
    setMobileTouched(true)
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (!passwordValid) {
      return
    }

    if (!confirmPasswordValid) {
      return
    }

    if (!mobileDigits.length || !mobileValid) {
      setMobileTouched(true)
      return
    }

    onSubmit({
      password,
      confirm_password: confirmPassword,
      mobile_number: mobileDigits,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => handlePasswordChange(e.target.value)}
          maxLength={PASSWORD_MAX_LENGTH}
          required
        />

        {password.length > 0 && (
          <div className="flex flex-col gap-1">
            {passwordRules.map((rule) => {
              const valid = passwordValidation[rule.key]

              return (
                <p
                  key={rule.key}
                  className={`text-xs ${
                    valid ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {valid ? '✓' : '✕'} {rule.label}
                </p>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <Input
          label="Confirm password"
          type="password"
          value={confirmPassword}
          onChange={(e) =>
            handleConfirmPasswordChange(e.target.value)
          }
          maxLength={PASSWORD_MAX_LENGTH}
          required
        />

        {confirmPassword.length > 0 && (
          <p
            className={`text-xs ${
              confirmPasswordValid
                ? 'text-green-600'
                : 'text-red-600'
            }`}
          >
            {confirmPasswordValid
              ? '✓ Passwords match.'
              : '✕ Passwords do not match.'}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <Input
          label="Mobile number"
          type="tel"
          value={mobileNumber}
          onChange={(e) => handleMobileChange(e.target.value)}
          onBlur={() => setMobileTouched(true)}
          maxLength={15}
          placeholder="Enter your mobile number"
          required
        />

        {mobileTouched && (
          <p
            className={`text-xs ${
              mobileValid && mobileDigits.length > 0
                ? 'text-green-600'
                : 'text-red-600'
            }`}
          >
            {mobileValid && mobileDigits.length > 0
              ? '✓ Valid mobile number format.'
              : '✕ Enter a valid mobile number.'}
          </p>
        )}
      </div>

      <Button
        type="submit"
        isLoading={isLoading}
        disabled={!formValid || isLoading}
        className="w-full"
      >
        Continue
      </Button>
    </form>
  )
}