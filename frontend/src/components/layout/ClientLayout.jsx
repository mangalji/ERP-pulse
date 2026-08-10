import { useState, useEffect, useRef } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

/**
 * All possible sidebar items. Each item maps to a module code.
 * Items without a module_code are always shown (Dashboard, Profile, Notifications, Settings).
 */
const ALL_NAV_ITEMS = [
  { to: '/app', label: 'Dashboard', icon: DashboardIcon, end: true, module: 'dashboard' },
  { to: '/app/invoice-reader', label: 'Invoice Reader', icon: InvoiceIcon, module: 'invoice_reader' },
  { to: '/app/ocr-jobs', label: 'OCR Jobs', icon: OcrIcon, module: 'ocr' },
  { to: '/app/ai-assistant', label: 'AI Assistant', icon: SparkleIcon, module: 'ai' },
  { to: '/app/employees', label: 'Employees', icon: EmployeesIcon, module: 'employees' },
  { to: '/app/reports', label: 'Reports', icon: ReportIcon, module: 'reports' },
  { to: '/app/reports-engine', label: 'Reports Engine', icon: ReportEngineIcon, module: 'reports' },
  { to: '/app/analytics', label: 'Analytics', icon: AnalyticsIcon, module: 'bi' },
  { to: '/app/notifications', label: 'Notifications', icon: BellIcon, module: 'notifications' },
  { to: '/app/settings', label: 'Company Settings', icon: GearIcon, module: null },
]

/* Employee-only items that always show for any authenticated user */
const EMPLOYEE_ALWAYS_ITEMS = ['/app/notifications', '/app/settings', '/app/profile']

const QUICK_ACTIONS = [
  {
    to: '/app/invoice-reader',
    label: 'Upload Invoice',
    icon: InvoiceIcon,
    module: 'invoice_reader',
    permission: 'ocr.upload',
  },
  {
    to: '/app/employees',
    label: 'Add Employee',
    icon: EmployeesIcon,
    module: 'employees',
    permission: 'employee.manage',
  },
  {
    to: '/app/employees',
    label: 'Invite Employee',
    icon: EmployeesIcon,
    module: 'employees',
    permission: 'employee.manage',
  },
  {
    to: '/app/integrations/netsuite',
    label: 'Connect NetSuite',
    icon: NetSuiteIcon,
    module: null,
    permission: null,
  },
  {
    to: '/app/reports-engine/generate',
    label: 'Generate Report',
    icon: ReportEngineIcon,
    module: 'reports',
    permission: 'reports.view',
  },
  {
    to: '/app/ai-assistant',
    label: 'Open AI Assistant',
    icon: SparkleIcon,
    module: 'ai',
    permission: 'ai.chat',
  },
]

/**
 * Reusable Client Company Portal layout.
 * Top navbar + sidebar + breadcrumb + page header + profile menu + notifications.
 */
export default function ClientLayout({ title, breadcrumb, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [availableModules, setAvailableModules] = useState([])
  const userMenuRef = useRef(null)
  const notifRef = useRef(null)

  const isCompanyAdmin = user?.is_superadmin || user?.is_staff || (user?.roles || []).includes('company_admin')

  const loadUnread = async () => {
    try {
      const res = await clientApi.getUnreadNotificationCount()
      setUnreadCount(res?.count ?? 0)
    } catch {
      setUnreadCount(0)
    }
  }

  const loadNotifications = async () => {
    try {
      const res = await clientApi.fetchNotifications({ limit: 10, offset: 0 })
      setNotifications(res?.results ?? res ?? [])
    } catch {
      setNotifications([])
    }
  }

  useEffect(() => {
    loadUnread()
  }, [])

  useEffect(() => {
    const loadModules = async () => {
      try {
        const res = await clientApi.getMe()
        setAvailableModules(res?.modules || [])
      } catch {
        setAvailableModules([])
      }
    }
    loadModules()
  }, [])

  useEffect(() => {
    function handleClickOutside(event) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setUserMenuOpen(false)
      }
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setNotifOpen(false)
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

  const handleNotifToggle = () => {
    const next = !notifOpen
    setNotifOpen(next)
    if (next) loadNotifications()
  }

  const handleMarkAllRead = async () => {
    try {
      await clientApi.markAllNotificationsRead()
      setUnreadCount(0)
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch {
      // noop
    }
  }

  const initials = user
    ? `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U'
    : 'U'

  const currentPath = location.pathname
  const activeNav = ALL_NAV_ITEMS.find((item) =>
    item.end ? currentPath === item.to : currentPath.startsWith(item.to),
  )

  const userModules = user?.modules || availableModules
  const userPermissions = user?.permissions || []

  const visibleNav = ALL_NAV_ITEMS.filter((item) => {
    if (!item.module) return true
    if (isCompanyAdmin) return true
    const hasModule = userModules.some((m) => m.module_code === item.module)
    if (!hasModule) return false
    // TASK 5: Employee Module Access — even if the company has the module,
    // the employee's role must grant the corresponding permission.
    // We map module codes to permission codes for this check.
    const modulePermissionMap = {
      'invoice_reader': 'ocr.upload',
      'ocr': 'ocr.upload',
      'ai': 'ai.chat',
      'employees': 'employee.manage',
      'reports': 'reports.view',
      'reports_engine': 'reports.view',
      'analytics': 'reports.view',
      'dashboard': 'dashboard.view',
    }
    const permCode = modulePermissionMap[item.module]
    if (permCode) {
      return userPermissions.includes(permCode)
    }
    return true
  })

  const visibleQuickActions = QUICK_ACTIONS

    return (
      <div className="flex min-h-screen bg-[var(--color-canvas)]">
        {sidebarOpen && (
          <button
            aria-label="Close menu"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          />
        )}
  
        {/* Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-[var(--color-sidebar)] px-4 py-6
            transition-transform lg:static lg:translate-x-0
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
        >
          <div className="mb-8 flex items-center gap-2 px-2">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-bold text-white">
              E
            </span>
            <span className="font-[var(--font-display)] text-lg font-semibold text-white">ERP Pulse</span>
          </div>
  
          <nav className="flex flex-1 flex-col gap-1">
            {visibleNav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-[var(--color-sidebar-soft)] text-white'
                      : 'text-[var(--color-sidebar-ink)] hover:bg-[var(--color-sidebar-soft)] hover:text-white'
                  }`
                }
              >
                <Icon className="h-4.5 w-4.5 shrink-0" />
                {label}
              </NavLink>
            ))}
                    {visibleQuickActions.length > 0 && (
              <div className="mt-5 border-t border-[var(--color-sidebar-soft)] pt-4">
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-sidebar-ink)]">
                  Quick Actions
                </p>
                <div className="flex flex-col gap-1">
                  {visibleQuickActions.map(({ to, label, icon: Icon }) => (
                    <NavLink
                      key={`${to}-${label}`}
                      to={to}
                      onClick={() => setSidebarOpen(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--color-sidebar-ink)] transition-colors hover:bg-[var(--color-sidebar-soft)] hover:text-white"
                    >
                      <Icon className="h-4.5 w-4.5 shrink-0" />
                      {label}
                    </NavLink>
                  ))}
                </div>
              </div>
            )}
          </nav>
  
          <div className="mt-4 flex flex-col gap-1">
            <NavLink
              to="/app/profile"
              onClick={() => setSidebarOpen(false)}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--color-sidebar-ink)] hover:bg-[var(--color-sidebar-soft)] hover:text-white"
            >
              <ProfileIcon className="h-4.5 w-4.5 shrink-0" />
              Profile
            </NavLink>
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--color-negative)] hover:bg-[var(--color-sidebar-soft)]"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4.5 w-4.5 shrink-0">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
              Logout
            </button>
          </div>
        </aside>
  
        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top navbar */}
          <header className="flex h-16 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 sm:px-6">
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
              {/* Notification bell */}
              <div className="relative" ref={notifRef}>
                <button
                  onClick={handleNotifToggle}
                  aria-label="Notifications"
                  className="relative rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
                  </svg>
                  {unreadCount > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-negative)] px-1 text-[10px] font-bold text-white">
                      {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                  )}
                </button>
                {notifOpen && (
                  <div className="absolute right-0 mt-2 w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg">
                    <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
                      <p className="text-sm font-semibold text-[var(--color-ink)]">Notifications</p>
                      <button
                        onClick={handleMarkAllRead}
                        className="text-xs font-medium text-[var(--color-primary)] hover:underline"
                      >
                        Mark all read
                      </button>
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <p className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">No notifications</p>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            className={`border-b border-[var(--color-border)] px-4 py-3 last:border-0 ${n.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}
                          >
                            <p className="text-sm font-medium text-[var(--color-ink)]">{n.title}</p>
                            {n.message && <p className="mt-0.5 text-xs text-[var(--color-muted)]">{n.message}</p>}
                          </div>
                        ))
                      )}
                    </div>
                    <NavLink
                      to="/app/notifications"
                      onClick={() => setNotifOpen(false)}
                      className="block border-t border-[var(--color-border)] px-4 py-2 text-center text-sm font-medium text-[var(--color-primary)] hover:bg-[var(--color-canvas)]"
                    >
                      View all
                    </NavLink>
                  </div>
                )}
              </div>
  
              {/* User menu */}
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen((prev) => !prev)}
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
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2 shadow-lg">
                    <div className="px-4 py-3">
                      <p className="text-sm font-semibold text-[var(--color-ink)]">
                        {user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--color-muted)]">{user?.email || ''}</p>
                    </div>
                    <div className="border-t border-[var(--color-border)]" />
                    <NavLink
                      to="/app/profile"
                      onClick={() => setUserMenuOpen(false)}
                      className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]"
                    >
                      Profile
                    </NavLink>
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
  
          {/* Breadcrumb */}
          <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 sm:px-6">
            <nav className="text-xs text-[var(--color-muted)]">
              <span>Client Portal</span>
              <span className="mx-1.5">/</span>
              <span className="font-medium text-[var(--color-ink)]">{breadcrumb || activeNav?.label || title}</span>
            </nav>
          </div>
  
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
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
function InvoiceIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M12 18v-6M9 15l3 3 3-3" />
    </svg>
  )
}
function OcrIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2" />
      <path d="M8 12h.01M12 12h.01M16 12h.01" />
    </svg>
  )
}
function SparkleIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M12 3l1.8 4.9L19 9.5l-5.2 1.6L12 16l-1.8-4.9L5 9.5l5.2-1.6L12 3Z" />
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
function ReportIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M9 12h6M9 16h6M9 8h3" />
    </svg>
  )
}
function ReportEngineIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h6M9 9h2" />
    </svg>
  )
}
function AnalyticsIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M3 3v18h18" />
      <path d="M7 15l4-4 3 3 5-6" />
    </svg>
  )
}
function BellIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
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
function NetSuiteIcon(props) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      {...props}
    >
      <path d="M7 4h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
      <path d="M9 8h6M9 12h6M9 16h3" />
    </svg>
  )
}
function ProfileIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
    </svg>
  )
}