import { useState, useEffect, useRef } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import ThemeToggle from './ThemeToggle.jsx'
import ProfileAvatar from '../ui/ProfileAvatar.jsx'
import PageTransition from '../../motion/PageTransition.jsx'
import Popover from '../../motion/Popover.jsx'
import AmbientBackground from '../../motion/AmbientBackground.jsx'
import { gsap, useGSAP, prefersReducedMotion, EASE, hasPlayedShell, markShellPlayed } from '../../motion/gsap.js'

const NAV_ITEMS = [
  { to: '/admin', label: 'Dashboard', icon: DashboardIcon, end: true },
  { to: '/admin/companies', label: 'Companies', icon: BuildingIcon },
  { to: '/admin/plans', label: 'Plans', icon: PlanIcon },
  { to: '/admin/employees', label: 'Employees', icon: EmployeesIcon },
  // { to: '/admin/profile', label: 'Settings', icon: GearIcon },
]

/**
 * Reusable AGSuite Super Admin layout.
 * Top navbar + collapsible left sidebar + content area + breadcrumb.
 */
export default function AdminLayout({ title, breadcrumb, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef(null)
  const shell = useRef(null)

  // One-time shell intro: sidebar nav cascades in, header drops down.
  // Guarded so it plays once per tab, not on every page's AdminLayout remount.
  useGSAP(() => {
    if (prefersReducedMotion() || hasPlayedShell('admin-shell')) return
    markShellPlayed('admin-shell')
    gsap.timeline({ defaults: { ease: EASE } })
      .fromTo('.shell-nav-item', { x: -20, opacity: 0 }, { x: 0, opacity: 1, stagger: 0.07, duration: 0.6, clearProps: 'all' }, 0.1)
      .fromTo('.shell-header', { y: -30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, clearProps: 'all' }, 0)
  }, { scope: shell })

  useEffect(() => {
    function handleClickOutside(event) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    setUserMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user
    ? `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U'
    : 'U'

  const currentPath = location.pathname
  const activeNav = NAV_ITEMS.find((item) =>
    item.end ? currentPath === item.to : currentPath.startsWith(item.to),
  )

  return (
    <div ref={shell} className="relative flex min-h-screen bg-[var(--color-canvas)]">
      <AmbientBackground />
      {/* Mobile overlay */}
      {sidebarOpen && (
        <button
          aria-label="Close menu"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`shell-sidebar fixed inset-y-0 left-0 z-40 flex flex-col bg-[var(--color-sidebar)] px-4 py-6
          transition-[width] duration-300 max-lg:transition-transform lg:static lg:translate-x-0
          ${collapsed ? 'lg:w-20' : 'lg:w-64'}
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <NavLink to="/admin" onClick={(event) => {
            if (location.pathname === '/admin') {
              event.preventDefault()
              window.location.reload()
            }
          }} className={`mb-8 flex items-center gap-2 px-2 ${
            collapsed ? 'lg:justify-center' : ''
          }`}
          aria-label="Go to Dashboard">
          {!collapsed && (
            <span className="font-[var(--font-display)] text-lg font-semibold text-white">
              AGSuite
            </span>
          )}
        </NavLink>
        
        <div className={`mb-4 flex ${collapsed ? 'justify-center' : 'justify-end'}`}>
          <button
            type="button"
            onClick={() => setCollapsed((prev) => !prev)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-2xl leading-none text-[var(--color-sidebar-ink)] transition-colors hover:bg-[var(--color-sidebar-soft)] hover:text-white"
          >
            {collapsed ? '›' : '‹'}
          </button>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `shell-nav-item group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-200 ${
                  collapsed ? 'lg:justify-center lg:px-0' : ''
                } ${
                  isActive
                    ? 'bg-[var(--color-sidebar-soft)] text-white'
                    : 'text-[var(--color-sidebar-ink)] hover:bg-[var(--color-sidebar-soft)] hover:text-white'
                }`
              }
            >
              <Icon className="h-4.5 w-4.5 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 flex flex-col gap-1">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--color-negative)] hover:bg-[var(--color-sidebar-soft)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5 shrink-0">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
            </svg>
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top navbar */}
        <header className="shell-header sticky top-0 z-20 flex min-h-16 items-center justify-between gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-3 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
              className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] lg:hidden"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            <span className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              {title}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            {/* User menu */}
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen((prev) => !prev)}
                className="flex items-center gap-2 rounded-full bg-[var(--color-primary-soft)] px-2 py-1 pr-1 text-sm font-semibold text-[var(--color-primary-dark)] hover:bg-[var(--color-primary-soft)] transition-colors"
                aria-label="User menu"
              >
                <ProfileAvatar profilePicture={user?.profile_pic} initials={initials} className="h-7 w-7" />
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3 w-3">
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
              {userMenuOpen && (
                <Popover className="absolute right-0 z-50 mt-2 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2 shadow-xl">
                  <div className="px-4 py-3">
                    <p className="text-sm font-semibold text-[var(--color-ink)]">
                      {user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--color-muted)]">{user?.email || ''}</p>
                  </div>
                  <div className="border-t border-[var(--color-border)]" />
                  <NavLink
                    to="/admin/profile"
                    onClick={() => setUserMenuOpen(false)}
                    className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]"
                  >
                    Profile
                  </NavLink>
                  <NavLink
                    to="/admin/company-logs"
                    onClick={() => setUserMenuOpen(false)}
                    className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]"
                  >
                    Companies Logs
                  </NavLink>
                  <button
                    onClick={handleLogout}
                    className="block w-full px-4 py-2 text-left text-sm text-[var(--color-negative)] hover:bg-[var(--color-canvas)]"
                  >
                    Logout
                  </button>
                </Popover>
              )}
            </div>
          </div>
        </header>

        {/* Breadcrumb + page header */}
        <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 sm:px-6">
          <nav className="text-xs text-[var(--color-muted)]">
            <span>AGSuite</span>
            <span className="mx-1.5">/</span>
            <span className="font-medium text-[var(--color-ink)]">{breadcrumb || activeNav?.label || title}</span>
          </nav>
        </div>

        <PageTransition className="relative z-10 min-w-0 flex-1 px-3 py-4 sm:px-6 sm:py-6 lg:px-8">{children}</PageTransition>
      </div>
    </div>
  )
}

function DashboardIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  )
}
function BuildingIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M3 21h18" />
      <path d="M5 21V7l7-4 7 4v14" />
      <path d="M9 21v-6h6v6" />
    </svg>
  )
}
function PlanIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M12 18v-6M9 15l3 3 3-3" />
    </svg>
  )
}
function EmployeesIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 21v-2a6 6 0 0 1 12 0v2" />
      <path d="M16 4a3 3 0 0 1 0 6M21 21v-2a6 6 0 0 0-4-5.7" />
    </svg>
  )
}
function GearIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  )
}
