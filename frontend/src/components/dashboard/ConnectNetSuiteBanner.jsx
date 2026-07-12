import { Link } from 'react-router-dom'
import Button from '../ui/Button.jsx'

export default function ConnectNetSuiteBanner() {
  return (
    <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-[var(--color-netsuite)]/30 bg-[var(--color-netsuite-soft)] p-5 sm:flex-row sm:items-center">
      <div>
        <p className="text-sm font-semibold text-[var(--color-netsuite)]">NetSuite not connected</p>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
          Connect your NetSuite account to replace this dummy data with your real business metrics.
        </p>
      </div>
      <Link to="/connect-netsuite" className="shrink-0">
        <Button intent="netsuite">Connect NetSuite</Button>
      </Link>
    </div>
  )
}
