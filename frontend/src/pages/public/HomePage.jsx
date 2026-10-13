import { Link } from 'react-router-dom'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'

const FEATURES = [
  {
    title: 'NetSuite Integration',
    description: 'Seamlessly connect and sync data with Oracle NetSuite. Real-time inventory, orders, and financial updates.',
    icon: 'netsuite',
  },
  {
    title: 'OCR',
    description: 'Extract structured data from invoices and documents with advanced OCR. Reduce manual data entry significantly.',
    icon: 'ocr',
  },
  {
    title: 'AI Assistant',
    description: 'Get intelligent insights and answers from your business data. AI-powered analysis of invoices, reports, and trends.',
    icon: 'ai',
  },
  {
    title: 'Multi Tenant',
    description: 'Isolated workspaces for each company. Secure, scalable multi-tenancy with complete data segregation.',
    icon: 'tenant',
  },
  {
    title: 'Role Based Access',
    description: 'Granular permissions with role-based access control. Ensure the right people have the right access.',
    icon: 'rbac',
  },
]

const ICONS = {
  netsuite: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  ),
  ocr: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 15l3 3 3-3" />
    </svg>
  ),
  ai: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
      <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a2 2 0 0 1 0 4h-1a7 7 0 0 1-7 7h-1a2 2 0 0 1-2-2v-1.27A2 2 0 0 1 6 16a2 2 0 0 1-2-2 2 2 0 0 1 2-2c.74 0 1.39.4 1.73 1H7v-1a7 7 0 0 1 7-7h1V5.27A2 2 0 0 1 16 4a2 2 0 0 1 2 2v1.27A2 2 0 0 1 20 8a2 2 0 0 1-2 2c-.74 0-1.39-.4-1.73-1H11v1a7 7 0 0 1-7 7H3a2 2 0 0 1 0-4h1a7 7 0 0 1 7-7h1V5.27c.34-.61 1-1.27 1.73-1.27z" />
    </svg>
  ),
  tenant: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <path d="M9 22V12h6v10" />
    </svg>
  ),
  rbac: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
}

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-[var(--color-primary)]/5 to-transparent" />
        <div className="mx-auto max-w-7xl px-4 pt-12 pb-0 sm:px-6 sm:pt-14 lg:px-8 lg:pt-16">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="font-[var(--font-display)] text-4xl font-bold tracking-tight text-[var(--color-ink)] sm:text-5xl lg:text-6xl">
              AGSuite ERP
            </h1>
            <p className="mt-6 text-lg leading-8 text-[var(--color-muted)]">
              Transform your business operations with AI-driven invoice processing, NetSuite integration,
              and powerful analytics. The all-in-one platform for modern enterprises.
            </p>

            <div className="mt-8 flex justify-center">
              <Link to="/login">
                <Button intent="primary" size="lg" className="px-8 sm:px-30 text-base sm:text-lg">
                  Login
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Features Preview */}
      <section className="pt-6 pb-16 sm:pt-8 sm:pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)]">
              Everything you need to scale
            </h2>
            <p className="mt-4 text-lg text-[var(--color-muted)]">
              From invoice processing to executive dashboards, AGSuite ERP covers every layer of your business.
            </p>
          </div>
          <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-6 lg:gap-8">
            {FEATURES.map((feature) => (
              <Card key={feature.title} className="p-6 sm:col-span-1 lg:col-span-2">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                  {ICONS[feature.icon]}
                </div>
                <h3 className="mt-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm text-[var(--color-muted)]">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)]">
              Ready to transform your business?
            </h2>
            <p className="mt-4 text-lg text-[var(--color-muted)]">
              See AGSuite ERP in action. Book a demo with our team today.
            </p>
            </div>
        </div>
      </section>
    </div>
  )
}
