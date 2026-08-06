import { Link } from 'react-router-dom'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'

const FEATURES = [
  {
    title: 'NetSuite Integration',
    description: 'Seamlessly connect and sync data with Oracle NetSuite. Real-time inventory, orders, and financial updates.',
    details: [
      'OAuth 2.0 secure connection',
      'Real-time data synchronization',
      'SuiteQL-powered analytics',
      'Automatic token refresh',
      'Company-scoped connections',
      'Employee-to-connection mapping',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
      </svg>
    ),
  },
  {
    title: 'OCR',
    description: 'Extract structured data from invoices and documents with advanced OCR. Reduce manual data entry significantly.',
    details: [
      'PDF, PNG, JPG support',
      'SHA256 duplicate detection',
      'Async Celery processing',
      'Gemini-powered extraction',
      'Confidence scoring',
      'Versioned document history',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6M9 15l3 3 3-3" />
      </svg>
    ),
  },
  {
    title: 'AI Assistant',
    description: 'Get intelligent insights and answers from your business data. AI-powered analysis of invoices, reports, and trends.',
    details: [
      'Company-data-backed context',
      'Invoice and OCR tool integration',
      'Capability-driven pipeline',
      'Conversation history',
      'Audit logging',
      'Graceful fallbacks',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a2 2 0 0 1 0 4h-1a7 7 0 0 1-7 7h-1a2 2 0 0 1-2-2v-1.27A2 2 0 0 1 6 16a2 2 0 0 1-2-2 2 2 0 0 1 2-2c.74 0 1.39.4 1.73 1H7v-1a7 7 0 0 1 7-7h1V5.27A2 2 0 0 1 16 4a2 2 0 0 1 2 2v1.27A2 2 0 0 1 20 8a2 2 0 0 1-2 2c-.74 0-1.39-.4-1.73-1H11v1a7 7 0 0 1-7 7H3a2 2 0 0 1 0-4h1a7 7 0 0 1 7-7h1V5.27c.34-.61 1-1.27 1.73-1.27z" />
      </svg>
    ),
  },
  {
    title: 'Reports',
    description: 'Generate comprehensive business reports on demand. Sales, purchase, inventory, and financial analytics.',
    details: [
      'Sales trend analysis',
      'Purchase order reports',
      'Customer analytics',
      'Inventory valuation',
      'Finance summaries',
      'Multiple export formats',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M18 20V10M12 20V4M6 20v-6" />
      </svg>
    ),
  },
  {
    title: 'BI Dashboard',
    description: 'Executive dashboard with real-time KPIs, charts, and activity feeds. Make data-driven decisions instantly.',
    details: [
      '14+ KPI cards',
      'Real-time charts',
      'Activity feed',
      'Quick actions',
      'NetSuite-driven metrics',
      'AI-generated insights',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    title: 'Multi Tenant',
    description: 'Isolated workspaces for each company. Secure, scalable multi-tenancy with complete data segregation.',
    details: [
      'Company-scoped data',
      'Tenant middleware',
      'Isolated employee management',
      'Per-company modules',
      'Secure by design',
      'Scalable architecture',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <path d="M9 22V12h6v10" />
      </svg>
    ),
  },
  {
    title: 'Role Based Access',
    description: 'Granular permissions with role-based access control. Ensure the right people have the right access.',
    details: [
      'Custom role creation',
      'Permission matrices',
      'Super Admin / Company Admin / Employee',
      'Audit logging',
      'Feature-level access',
      'Company-scoped roles',
    ],
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-8 w-8">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
]

export default function FeaturesPage() {
  return (
    <div className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="font-[var(--font-display)] text-3xl font-bold text-[var(--color-ink)] sm:text-4xl">
            Powerful Features for Modern Business
          </h1>
          <p className="mt-4 text-lg text-[var(--color-muted)]">
            ERP Pulse combines OCR, AI, NetSuite integration, and business intelligence into one unified platform.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-2">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="p-8">
              <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                {feature.icon}
              </div>
              <h3 className="mt-6 font-[var(--font-display)] text-xl font-semibold text-[var(--color-ink)]">
                {feature.title}
              </h3>
              <p className="mt-2 text-[var(--color-muted)]">{feature.description}</p>
              <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {feature.details.map((detail) => (
                  <li key={detail} className="flex items-center gap-2 text-sm text-[var(--color-ink-soft)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-positive)]" />
                    {detail}
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>

        <div className="mt-16 text-center">
          <Link to="/request-demo">
            <Button intent="primary" size="lg">Request Demo</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
