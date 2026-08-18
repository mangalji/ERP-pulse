export const COUNTRY_OPTIONS = [
  { value: 'IN', label: 'India', dialCode: '+91', minDigits: 10, maxDigits: 10, example: '9876543210' },
  { value: 'US', label: 'United States', dialCode: '+1', minDigits: 10, maxDigits: 10, example: '2025550123' },
  { value: 'GB', label: 'United Kingdom', dialCode: '+44', minDigits: 10, maxDigits: 10, example: '7400123456' },
  { value: 'AU', label: 'Australia', dialCode: '+61', minDigits: 9, maxDigits: 9, example: '412345678' },
  { value: 'CA', label: 'Canada', dialCode: '+1', minDigits: 10, maxDigits: 10, example: '4165550123' },
  { value: 'AE', label: 'United Arab Emirates', dialCode: '+971', minDigits: 9, maxDigits: 9, example: '501234567' },
  { value: 'SG', label: 'Singapore', dialCode: '+65', minDigits: 8, maxDigits: 8, example: '81234567' },
  { value: 'DE', label: 'Germany', dialCode: '+49', minDigits: 10, maxDigits: 11, example: '15123456789' },
  { value: 'FR', label: 'France', dialCode: '+33', minDigits: 9, maxDigits: 9, example: '612345678' },
  { value: 'JP', label: 'Japan', dialCode: '+81', minDigits: 10, maxDigits: 10, example: '9012345678' },
]

export const NAME_MAX_LENGTH = 20
export const EMAIL_MAX_LENGTH = 40

const NAME_REGEX = /^[A-Za-zÀ-ÖØ-öø-ÿ' -]+$/
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const REPEATED_CHARACTER_REGEX = /(.)\1{4,}/u
const ALL_SAME_CHARACTER_REGEX = /^(.)\1*$/u
const PHONE_LONG_REPEAT_REGEX = /(\d)\1{5,}/

export function validateName(value, label = 'Name') {
  const valueTrimmed = value.trim()

  if (!valueTrimmed) {
    return `${label} is required.`
  }

  if (valueTrimmed.length < 2) {
    return `${label} must contain at least 2 characters.`
  }

  if (valueTrimmed.length > NAME_MAX_LENGTH) {
    return `${label} must not exceed ${NAME_MAX_LENGTH} characters.`
  }

  if (!NAME_REGEX.test(valueTrimmed)) {
    return `${label} may contain letters, spaces, hyphens, and apostrophes only.`
  }

  const compact = valueTrimmed.replace(/[^A-Za-z0-9]/g, '')

  if (ALL_SAME_CHARACTER_REGEX.test(compact)) {
    return `${label} must look like a realistic name.`
  }

  if (REPEATED_CHARACTER_REGEX.test(valueTrimmed)) {
    return `${label} cannot contain the same character more than 4 times continuously.`
  }

  return ''
}

export function validateEmail(value) {
  const email = value.trim()

  if (!email) {
    return 'Email is required.'
  }

  if (email.length > EMAIL_MAX_LENGTH) {
    return `Email must not exceed ${EMAIL_MAX_LENGTH} characters.`
  }

  if (!EMAIL_REGEX.test(email)) {
    return 'Enter a valid email address.'
  }

  if (REPEATED_CHARACTER_REGEX.test(email)) {
    return 'Email cannot contain the same character more than 4 times continuously.'
  }

  return ''
}

const COMPANY_NAME_REGEX =
  /^[A-Za-z0-9À-ÖØ-öø-ÿ&().,'\- ]+$/

const COMPANY_CODE_REGEX =
  /^[A-Za-z0-9_-]+$/

export function validateCompanyText(value, label = 'Company name') {
  const text = String(value || '').trim()

  if (!text) {
    return `${label} is required.`
  }

  if (text.length < 3) {
    return `${label} must contain at least 3 characters.`
  }

  if (text.length > 100) {
    return `${label} must not exceed 100 characters.`
  }

  if (!/^[A-Za-z0-9À-ÖØ-öø-ÿ&().,'\- ]+$/.test(text)) {
    return `${label} contains unsupported characters.`
  }

  const compact = text.replace(/[^A-Za-z0-9]/g, '')

  if (!compact || ALL_SAME_CHARACTER_REGEX.test(compact)) {
    return `${label} must look like a realistic name.`
  }

  if (REPEATED_CHARACTER_REGEX.test(text)) {
    return `${label} cannot contain the same character more than 4 times continuously.`
  }

  return ''
}

export function validateCompanyCode(value) {
  const code = String(value || '').trim()

  if (!code) {
    return 'Company code is required.'
  }

  if (code.length < 2) {
    return 'Company code must contain at least 2 characters.'
  }

  if (code.length > 20) {
    return 'Company code must not exceed 20 characters.'
  }

  if (!/^[A-Za-z0-9_-]+$/.test(code)) {
    return 'Company code may contain letters, numbers, hyphens, and underscores only.'
  }

  if (ALL_SAME_CHARACTER_REGEX.test(code)) {
    return 'Company code must look realistic and cannot contain one repeated character only.'
  }

  if (REPEATED_CHARACTER_REGEX.test(code)) {
    return 'Company code cannot contain the same character more than 4 times continuously.'
  }

  return ''
}

export function getCountryRule(country) {
  return COUNTRY_OPTIONS.find((item) => item.value === country)
}

function validateIndiaPhonePattern(digits) {
  if (!digits) return ''

  const firstDigit = digits[0]

  if (!['6', '7', '8', '9'].includes(firstDigit)) {
    return 'Indian mobile numbers must start with 6, 7, 8, or 9.'
  }

  const firstDigitCount = [...digits].filter(
    (digit) => digit === firstDigit,
  ).length

  if (firstDigitCount >= 4) {
    return 'The first digit cannot repeat 4 or more times in the number.'
  }

  if (ALL_SAME_CHARACTER_REGEX.test(digits)) {
    return 'Mobile number cannot contain the same digit throughout.'
  }

  if (PHONE_LONG_REPEAT_REGEX.test(digits)) {
    return 'Mobile number cannot contain the same digit more than 5 times continuously.'
  }

  if (digits === '1234567890' || digits === '9876543210') {
    return 'Mobile number cannot be a simple sequential number.'
  }

  if (/^(\d)(\d)(?:\1\2){4}$/.test(digits)) {
    return 'Mobile number cannot follow a repeating two-digit pattern.'
  }

  return ''
}

export function validatePhone(value, country) {
  const digits = String(value || '').replace(/\D/g, '')
  const rule = getCountryRule(country)

  if (!country) {
    return 'Please select a country.'
  }

  if (!digits) {
    return 'Mobile number is required.'
  }

  if (!rule) {
    return 'Phone validation is unavailable for the selected country.'
  }

  if (digits.length < rule.minDigits) {
    return `Enter exactly ${rule.minDigits} digits. Example: ${rule.example}`
  }

  if (digits.length > rule.maxDigits) {
    return `Enter only ${rule.maxDigits} digits. Example: ${rule.example}`
  }

  if (country === 'IN') {
    return validateIndiaPhonePattern(digits)
  }

  return ''
}

export function validateGender(value) {
  if (!value) {
    return 'Please select a gender.'
  }

  return ''
}

export function validationState(message, touched) {
  if (!touched) {
    return 'neutral'
  }

  return message ? 'error' : 'success'
}