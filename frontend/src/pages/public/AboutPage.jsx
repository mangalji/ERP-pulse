import { Link } from 'react-router-dom'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'

const VALUES = [
  {
    title: 'Innovation First',
    description: 'We leverage cutting-edge AI and OCR technology to solve real business problems.',
  },
  {
    title: 'Customer Success',
    description: 'Every feature is built with our customers in mind. Your success is our success.',
  },
  {
    title: 'Security & Compliance',
    description: 'Enterprise-grade security with multi-tenancy, audit logging, and role-based access.',
  },
  {
    title: 'Seamless Integration',
    description: 'Built to work with your existing tools, especially Oracle NetSuite.',
  },
]

const STATS = [
  { value: '10+', label: 'Enterprise Features' },
  { value: '99.9%', label: 'Uptime SLA' },
  { value: '24/7', label: 'Support Available' },
  { value: '100+', label: 'Companies Served' },
]

export default function AboutPage() {
  return (
    <div className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)] sm:text-4xl">
            About AGSuite ERP
          </h1>
          <p className="mt-6 text-lg text-[var(--color-muted)]">
            AGSuite ERP is developed by AGSuite, a team passionate about eliminating manual data entry
            and empowering businesses with intelligent automation. Our platform combines OCR, AI,
            and NetSuite integration to create a seamless workflow from document capture to
            financial reporting.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat) => (
            <Card key={stat.label} className="p-6 text-center">
              <p className="font-mono-tabular text-3xl font-bold text-[var(--color-primary)]">{stat.value}</p>
              <p className="mt-2 text-sm text-[var(--color-muted)]">{stat.label}</p>
            </Card>
          ))}
        </div>

        <div className="mt-20">
          <h2 className="mx-auto max-w-2xl text-center font-[var(--font-display)] text-2xl font-bold text-[var(--color-ink)]">
            Our Values
          </h2>
          <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((value) => (
              <Card key={value.title} className="p-6">
                <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  {value.title}
                </h3>
                <p className="mt-2 text-sm text-[var(--color-muted)]">{value.description}</p>
              </Card>
            ))}
          </div>
        </div>

        <div className="mt-20 text-center">
          <Link to="/request-demo">
            <Button intent="primary" size="lg">Get Started</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
