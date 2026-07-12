import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import PulseIndicator from '../components/ui/PulseIndicator.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'

const BENEFITS = [
  {
    title: 'Live business metrics',
    text: 'Revenue, profit, and order data pulled directly from your NetSuite account — never a stale copy.',
  },
  {
    title: 'AI grounded in your data',
    text: 'The AI Assistant only reasons over your real NetSuite records, never invented numbers.',
  },
  {
    title: 'Read-only, always',
    text: 'ERP Pulse never writes back to NetSuite or modifies your business transactions.',
  },
]

export default function ConnectNetSuitePage() {
  const { netSuiteConnected, connectNetSuite } = useAuth()

  return (
    <DashboardLayout title="Connect NetSuite">
      <div className="mx-auto flex max-w-3xl flex-col items-center gap-8 py-8 text-center">
        <span className="relative inline-flex h-10 w-10 text-[var(--color-netsuite)]">
          <span className="pulse-ring absolute inset-0" />
          <span className="relative inline-flex h-full w-full rounded-full bg-current" />
        </span>

        <div>
          <h2 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)] sm:text-3xl">
            Bring your NetSuite data to life
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-[var(--color-muted)] sm:text-base">
            NetSuite stays the source of truth. ERP Pulse reads your data, never modifies it, and turns it
            into dashboards, reports, and AI insight.
          </p>
        </div>

        {netSuiteConnected ? (
          <Card className="flex items-center gap-3 px-6 py-4">
            <PulseIndicator state="connected" label="Your NetSuite account is connected" />
          </Card>
        ) : (
          <Button intent="netsuite" size="lg" onClick={connectNetSuite}>
            Connect NetSuite
          </Button>
        )}

        <div className="grid w-full gap-4 text-left sm:grid-cols-3">
          {BENEFITS.map((benefit) => (
            <Card key={benefit.title} className="p-5">
              <h3 className="font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
                {benefit.title}
              </h3>
              <p className="mt-1.5 text-xs text-[var(--color-muted)]">{benefit.text}</p>
            </Card>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}
