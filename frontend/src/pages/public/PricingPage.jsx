import { Link } from 'react-router-dom'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'

const PLANS = [
  {
    name: 'Starter',
    price: '₹9,999',
    period: '/month',
    description: 'Perfect for small teams getting started with automation.',
    features: [
      'Up to 10 employees',
      '100 OCR documents/month',
      '10 GB storage',
      'Basic reports',
      'Email support',
      'Single NetSuite connection',
    ],
    cta: 'Request Demo',
    highlighted: false,
  },
  {
    name: 'Professional',
    price: '₹24,999',
    period: '/month',
    description: 'For growing businesses that need more power and integrations.',
    features: [
      'Up to 50 employees',
      '500 OCR documents/month',
      '50 GB storage',
      'Advanced reports & BI dashboard',
      'Priority support',
      'Multiple NetSuite connections',
      'AI Assistant access',
      'Custom roles & permissions',
    ],
    cta: 'Request Demo',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'Tailored solutions for large organizations with advanced needs.',
    features: [
      'Unlimited employees',
      'Unlimited OCR documents',
      'Unlimited storage',
      'Custom reports & white-label',
      'Dedicated support',
      'Unlimited NetSuite connections',
      'Advanced AI models',
      'SSO & advanced security',
      'Custom integrations',
    ],
    cta: 'Request Demo',
    highlighted: false,
  },
]

export default function PricingPage() {
  return (
    <div className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)] sm:text-4xl">
            Simple, Transparent Pricing
          </h1>
          <p className="mt-4 text-lg text-[var(--color-muted)]">
            Choose the plan that fits your business. All plans include a 14-day free trial.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <Card
              key={plan.name}
              className={`relative p-8 ${
                plan.highlighted
                  ? 'ring-2 ring-[var(--color-primary)] shadow-lg'
                  : ''
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-[var(--color-primary)] px-3 py-1 text-xs font-semibold text-white">
                    Most Popular
                  </span>
                </div>
              )}
              <h3 className="font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                {plan.name}
              </h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="font-mono-tabular text-4xl font-bold text-[var(--color-ink)]">
                  {plan.price}
                </span>
                {plan.period && (
                  <span className="text-[var(--color-muted)]">{plan.period}</span>
                )}
              </div>
              <p className="mt-2 text-sm text-[var(--color-muted)]">{plan.description}</p>
              <ul className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm text-[var(--color-ink-soft)]">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-positive)]">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                <Link to="/request-demo">
                  <Button
                    intent={plan.highlighted ? 'primary' : 'secondary'}
                    size="md"
                    className="w-full"
                  >
                    {plan.cta}
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
