import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import PulseIndicator from '../ui/PulseIndicator.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function TopNav({ title, onMenuClick }) {
  const { user, netSuiteConnected, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  const handleLogout = async () => {
    setMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const handleProfile = () => {
    setMenuOpen(false)
    navigate('/settings')
  }

  const initials = user
    ? `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U'
    : 'U'

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="flex min-h-16 items-center justify-between gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-3 sm:px-6">
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
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((prev) => !prev)}
            className="flex items-center gap-2 rounded-full bg-[var(--color-primary-soft)] px-2 py-1 pr-1 text-sm font-semibold text-[var(--color-primary-dark)] hover:bg-[var(--color-primary-soft)] transition-colors"
            aria-label="User menu"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-bold text-white">
              {initials}
            </span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3 w-3">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
          {menuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2 shadow-lg">
              <div className="px-4 py-3">
                <p className="text-sm font-semibold text-[var(--color-ink)]">
                  {user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}
                </p>
                <p className="mt-0.5 text-xs text-[var(--color-muted)]">{user?.email || ''}</p>
              </div>
              <div className="border-t border-[var(--color-border)]" />
              <button
                onClick={handleProfile}
                className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]"
              >
                Profile
              </button>
              <button
                onClick={handleLogout}
                className="block w-full px-4 py-2 text-left text-sm text-[var(--color-negative)] hover:bg-[var(--color-canvas)]"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
