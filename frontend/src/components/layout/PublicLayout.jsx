import { Link } from 'react-router-dom'
import Button from '../ui/Button.jsx'

const NAV_LINKS = [
  { label: 'Home', to: '/' },
  { label: 'Features', to: '/features' },
  { label: 'Pricing', to: '/pricing' },
  { label: 'About', to: '/about' },
  { label: 'Contact', to: '/contact' },
]

export default function PublicLayout({ children }) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-canvas)]">
      <nav className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2">
            <span className="relative inline-flex h-2.5 w-2.5 text-[var(--color-positive)]">
              <span className="pulse-ring absolute inset-0" />
              <span className="relative inline-flex h-full w-full rounded-full bg-current" />
            </span>
            <span className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              AGSuite ERP
            </span>
          </Link>

          <div className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className="text-sm font-medium text-[var(--color-muted)] transition-colors hover:text-[var(--color-ink)]"
              >
                {link.label}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button intent="secondary" size="sm">Login</Button>
            </Link>
            <Link to="/request-demo">
              <Button intent="primary" size="sm">Request Demo</Button>
            </Link>
          </div>
        </div>
      </nav>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
            <div className="flex items-center gap-2">
              <span className="relative inline-flex h-2.5 w-2.5 text-[var(--color-positive)]">
                <span className="pulse-ring absolute inset-0" />
                <span className="relative inline-flex h-full w-full rounded-full bg-current" />
              </span>
              <span className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                AGSuite ERP
              </span>
            </div>
            <p className="text-center text-xs text-[var(--color-muted)] md:text-left">
              &copy; {new Date().getFullYear()} AGSuite ERP. All rights reserved. Developed by Raj Mangal.
            </p>
            <div className="flex items-center gap-4 text-xs text-[var(--color-muted)]">
              <Link to="/about" className="hover:text-[var(--color-ink)]">About</Link>
              <Link to="/contact" className="hover:text-[var(--color-ink)]">Contact</Link>
              <Link to="/request-demo" className="hover:text-[var(--color-ink)]">Request Demo</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
