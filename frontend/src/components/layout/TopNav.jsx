import { useNavigate } from 'react-router-dom'
import PulseIndicator from '../ui/PulseIndicator.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function TopNav({ title, onMenuClick }) {
  const { netSuiteConnected, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Open menu"
          className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] lg:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <h1 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <PulseIndicator
          state={netSuiteConnected ? 'connected' : 'disconnected'}
          label={netSuiteConnected ? 'NetSuite connected' : 'NetSuite not connected'}
        />
        <button
          onClick={handleLogout}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-primary-soft)] text-sm font-semibold text-[var(--color-primary-dark)]"
          title="Log out"
        >
          U
        </button>
      </div>
    </header>
  )
}
