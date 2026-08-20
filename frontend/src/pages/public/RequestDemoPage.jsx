import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { demoApi } from '../../services/demo.js'

export default function RequestDemoPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      const form = event.target
      await demoApi.submit({
        company_name: form.company_name.value,
        business_email: form.business_email.value,
        contact_person: form.contact_person.value,
        phone: form.phone.value,
        industry: form.industry.value,
        company_size: form.company_size.value,
        city: form.city.value,
        country: form.country.value,
        message: form.message.value,
      })
      setSubmitted(true)
      addToast('Demo request submitted successfully!', 'success')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to submit demo request', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="py-20">
        <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
          <Card className="p-12 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[var(--color-positive-soft)] text-[var(--color-positive)]">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-8 w-8">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <h1 className="mt-6 font-[var(--font-display)] text-2xl font-bold text-[var(--color-ink)]">
              Thank you!
            </h1>
            <p className="mt-4 text-[var(--color-muted)]">
              Our team will contact you shortly to schedule your personalized demo of ERP Pulse.
            </p>
            <div className="mt-8">
              <Link to="/">
                <Button intent="primary" size="md">Back to Home</Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="py-20">
      <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)] sm:text-4xl">
            Request a Demo
          </h1>
          <p className="mt-4 text-lg text-[var(--color-muted)]">
            See ERP Pulse in action. Fill out the form below and our team will get back to you within 24 hours.
          </p>
        </div>

        <Card className="mt-12 p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Company Name *</label>
                <input
                  type="text"
                  name="company_name"
                  required
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                  placeholder="Acme Inc"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Business Email *</label>
                <input
                  type="email"
                  name="business_email"
                  required
                  maxLength={50}
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                  placeholder="contact@company.com"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Contact Person *</label>
                <input
                  type="text"
                  name="contact_person"
                  required
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                  placeholder="John Doe"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Phone *</label>
                <input
                  type="tel"
                  name="phone"
                  required
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                  placeholder="+91 98765 43210"
                  maxLength={15}
                  minLength={10}

                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Industry *</label>
                <select
                  name="industry"
                  required
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select industry</option>
                  <option value="TECHNOLOGY">Technology</option>
                  <option value="MANUFACTURING">Manufacturing</option>
                  <option value="RETAIL">Retail</option>
                  <option value="FINANCE">Finance</option>
                  <option value="HEALTHCARE">Healthcare</option>
                  <option value="LOGISTICS">Logistics</option>
                  <option value="ECOMMERCE">E-commerce</option>
                  <option value="SERVICES">Professional Services</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--color-ink)]">Company Size *</label>
                <select
                  name="company_size"
                  required
                  className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                >
                  <option value="">Select size</option>
                  <option value="1-10">1-10 employees</option>
                  <option value="11-50">11-50 employees</option>
                  <option value="51-200">51-200 employees</option>
                  <option value="201-500">201-500 employees</option>
                  <option value="500+">500+ employees</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-ink)]">City *</label>
              <input
                type="text"
                name="city"
                required
                className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                placeholder="Mumbai"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-ink)]">Country *</label>
              <input
                type="text"
                name="country"
                required
                className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                placeholder="India"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--color-ink)]">Message (Optional)</label>
              <textarea
                name="message"
                rows="3"
                className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                placeholder="Tell us about your requirements..."
              />
            </div>
            <Button type="submit" isLoading={isSubmitting} className="w-full">
              Submit Request
            </Button>
          </form>
        </Card>
      </div>
      <Toast toasts={toasts} removeToast={removeToast} />
    </div>
  )
}
