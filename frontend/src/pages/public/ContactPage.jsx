import { useState } from 'react'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'

export default function ContactPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      addToast('Message sent successfully! We will get back to you soon.', 'success')
      event.target.reset()
    } catch {
      addToast('Failed to send message. Please try again.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)] sm:text-4xl">
            Contact Us
          </h1>
          <p className="mt-4 text-lg text-[var(--color-muted)]">
            Have questions? We would love to hear from you. Send us a message and we will respond as soon as possible.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Card className="p-8">
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink)]">First Name</label>
                    <input
                      type="text"
                      required
                      className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                      placeholder="John"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink)]">Last Name</label>
                    <input
                      type="text"
                      required
                      className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                      placeholder="Doe"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--color-ink)]">Email</label>
                  <input
                    type="email"
                    required
                    className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                    placeholder="john@company.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--color-ink)]">Company</label>
                  <input
                    type="text"
                    required
                    className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                    placeholder="Your Company"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--color-ink)]">Message</label>
                  <textarea
                    rows="4"
                    required
                    className="mt-1 block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none"
                    placeholder="Tell us about your needs..."
                  />
                </div>
                <Button type="submit" isLoading={isSubmitting} className="w-full">
                  Send Message
                </Button>
              </form>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Email</h3>
              <p className="mt-2 text-sm text-[var(--color-muted)]">contact@agsuiterp.com</p>
            </Card>
            <Card className="p-6">
              <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Phone</h3>
              <p className="mt-2 text-sm text-[var(--color-muted)]">+91 98765 43210</p>
            </Card>
            <Card className="p-6">
              <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Location</h3>
              <p className="mt-2 text-sm text-[var(--color-muted)]">
                AGSuite Technologies
                <br />
                Tech Park, Bangalore
                <br />
                India
              </p>
            </Card>
          </div>
        </div>
      </div>
      <Toast toasts={toasts} removeToast={removeToast} />
    </div>
  )
}
