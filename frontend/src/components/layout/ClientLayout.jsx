import { useState, useEffect, useRef } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

// const ALL_NAV_ITEMS = [
//   {
//     to: '/app',
//     label: 'Dashboard',
//     icon: DashboardIcon,
//     end: true,
//     module: null,
//   },
//   {
//     to: '/app/ocr-test',
//     label: 'OCR',
//     icon: OcrIcon,
//     module: null,
//   },
//   {
//     to: '/app/ai-assistant',
//     label: 'AI Assistant',
//     icon: SparkleIcon,
//     module: 'ai',
//   },
//   {
//     to: '/app/employees',
//     label: 'Employees',
//     icon: EmployeesIcon,
//     module: 'employees',
//   },
//   {
//     to: '/app/reports-engine/generate',
//     label: 'Generate Report',
//     icon: ReportEngineIcon,
//     module: 'reports',
//   },
//   {
//     to: '/app/analytics',
//     label: 'Analytics',
//     icon: AnalyticsIcon,
//     module: 'bi',
//   },
//   {
//     to: '/app/notifications',
//     label: 'Notifications',
//     icon: BellIcon,
//     module: 'notifications',
//   },
//   {
//     to: '/app/settings',
//     label: 'Company Settings',
//     icon: GearIcon,
//     module: null,
//   },
// ]
const SYSTEM_NAV_KEYS = {
  employees: 'employees',
  settings: 'settings',
}

/* Employee-only items that always show for any authenticated user */
// const EMPLOYEE_ALWAYS_ITEMS = ['/app/notifications', '/app/settings', '/app/profile']

/**
 * Reusable Client Company Portal layout.
 * Top navbar + sidebar + breadcrumb + page header + profile menu + notifications.
 */
export default function ClientLayout({ title, breadcrumb, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [availableModules, setAvailableModules] = useState([])
  const [companyName, setCompanyName] = useState('')
  const [databaseNavItems, setDatabaseNavItems] = useState([])
  // const [expandedMenuItems, setExpandedMenuItems] = useState({})
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
    const loadClientProfile = async () => {
      try {
        const res = await clientApi.getMe()
        setAvailableModules(res?.modules || [])
        setCompanyName(
          res?.company_name ||
          res?.company?.name ||
          '',
        )
      } catch {
        setAvailableModules([])
        setCompanyName('')
      }
    }
    loadClientProfile()
  }, [])

  useEffect(() => {
    const loadNavigationMenu = async () => {
      try {
        const res = await clientApi.getNavigationMenu()
        // console.log("database navigation:", res)
        setDatabaseNavItems(Array.isArray(res) ? res: [])
        // const menu = Array.isArray(res) ? (res[0] || null) : res
        // setDatabaseNavItems(menu ? [menu] : [])
      } catch (error) {
        console.error('Failed to load transaction navigation:', error)
        setDatabaseNavItems([])
      }
    }

    loadNavigationMenu()
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

  // const currentPath = location.pathname
  // const activeNav = ALL_NAV_ITEMS.find((item) =>
  // item.end ? currentPath === item.to : currentPath.startsWith(item.to),
  // )

  // const userModules = user?.modules || availableModules
  // const userPermissions = user?.permissions || []

  // const visibleNav = ALL_NAV_ITEMS.filter((item) => {
  //   if (!item.module) return true
  //   if (isCompanyAdmin) return true
  //   const hasModule = userModules.some((m) => m.module_code === item.module)
  //   if (!hasModule) return false
  //   const modulePermissionMap = {
  //     'invoice_reader': 'ocr.upload',
  //     'ocr': 'ocr.upload',
  //     'ai': 'ai.chat',
  //     'employees': 'employee.manage',
  //     'reports': 'reports.view',
  //     'reports_engine': 'reports.view',
  //     'analytics': 'reports.view',
  //     'dashboard': 'dashboard.view',
  //   }
  //   const permCode = modulePermissionMap[item.module]
  //   if (permCode) {
  //     return userPermissions.includes(permCode)
  //   }
  //   return true
  // })

  // const toggleDatabaseMenu = (key) => {
  //   setExpandedMenuItems((prev) => ({
  //     ...prev,
  //     [key]: !(prev[key] ?? true),
  //   }))
  // }

  const buildMenuSearch = (queryParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(queryParams || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        search.set(key, String(value))
      }
    })
    const text = search.toString()
    return text ? `?${text}` : ''
  }

  const renderDatabaseMenuItem = (item, level = 0) => {
    const children = Array.isArray(item?.children) ? item.children : []
    const hasChildren = children.length > 0
    const route = item.route ? `${item.route}${buildMenuSearch(item.query_params)}` : ''
    // const isExpanded = expandedMenuItems[item.key] ?? true

    // if (hasChildren) {
    if (level===0){
      return (
        <div key={item.key} className="group/top relative shrink-0">
          {route ? (
            <NavLink to={route} className={({ isActive }) => `flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'}`}>
              <span>{item.name}</span>
              {hasChildren && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5"><path d="m6 9 6 6 6-6" /></svg>
              )}
            </NavLink>
          ) : (
            <button type="button" className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]">
              <span>{item.name}</span>
              {hasChildren && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5"><path d="m6 9 6 6 6-6" /></svg>
              )}
            </button>
          )}
          {hasChildren && (
            <div className="invisible absolute left-0 top-full z-50 mt-1 min-w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1 opacity-0 shadow-xl transition-all group-hover/top:visible group-hover/top:opacity-100 group-focus-within/top:visible group-focus-within/top:opacity-100">
              {children.map((child) => renderDatabaseMenuItem(child, 1))}
            </div>
          )}
        </div>
      )
    }

    // if (!item.route) return null

    return (
      <div key={item.key} className="group/submenu relative">
        {route ? (
          <NavLink to={route} className={({ isActive }) => `flex w-full items-center justify-between gap-4 rounded-md px-3 py-2 text-left text-sm transition-colors ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink)] hover:bg-[var(--color-canvas)]'}`}>
            <span>{item.name}</span>
            {hasChildren && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5 shrink-0"><path d="m9 6 6 6-6 6" /></svg>}
          </NavLink>
        ) : (
          <button type="button" className="flex w-full items-center justify-between gap-4 rounded-md px-3 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]">
            <span>{item.name}</span>
            {hasChildren && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5 shrink-0"><path d="m9 6 6 6-6 6" /></svg>}
          </button>
        )}
        {hasChildren && (
          <div className="invisible absolute left-full top-0 z-50 ml-1 min-w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1 opacity-0 shadow-xl transition-all group-hover/submenu:visible group-hover/submenu:opacity-100 group-focus-within/submenu:visible group-focus-within/submenu:opacity-100">
            {children.map((child) => renderDatabaseMenuItem(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  const netSuiteNavItem = {
  to: isCompanyAdmin
    ? '/app/integrations/netsuite'
    : '/app/netsuite',
  label: isCompanyAdmin
    ? 'NetSuite Integration'
    : 'NetSuite',
  icon: NetSuiteIcon,
}

  const netSuiteQuickAction = {
  to: isCompanyAdmin
    ? '/app/integrations/netsuite'
    : '/app/netsuite',
  label: isCompanyAdmin
    ? 'Connect NetSuite'
    : 'NetSuite',
  icon: NetSuiteIcon,
}

    return (
      <div className="flex min-h-screen flex-col bg-[var(--color-canvas)]">
        <header className="relative z-50 border-b border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm">
          <div className="flex min-h-16 items-center justify-between gap-4 px-3 sm:px-6">
            <div className="flex min-w-0 flex-1 items-center gap-4">
              <NavLink to="/app" className="flex shrink-0 items-center gap-2" aria-label="Go to Dashboard">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-bold text-white">E</span>
                <span className="hidden font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)] sm:inline">AGSuite ERP</span>
              </NavLink>
              {/* <nav className="flex min-w-0 flex-1 flex-wrap items-center gap-1" aria-label="Main navigation">
                {databaseNavItems.length > 0 ? databaseNavItems.map((item) => renderDatabaseMenuItem(item, 0)) : (
                  [...visibleNav, netSuiteNavItem].map(({ to, label, end }) => (
                    <NavLink key={to} to={to} end={end} className={({ isActive }) => `shrink-0 rounded-md px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'}`}>{label}</NavLink>
                  ))
                )}
              </nav> */}
              {/* <nav className="flex flex-1 flex-col gap-1">
  {databaseNavItems.map((item) => renderDatabaseMenuItem(item, 0))}
</nav> */}
<nav
  className="flex min-w-0 flex-1 items-center gap-2 overflow-visible"
  aria-label="Main navigation"
>
  {databaseNavItems.map((item) => renderDatabaseMenuItem(item, 0))}
</nav>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="hidden max-w-48 truncate text-right lg:block">{companyName && <span className="text-sm font-semibold capitalize text-[var(--color-ink)]">{companyName}</span>}</div>
              <div className="relative" ref={notifRef}>
                <button onClick={handleNotifToggle} aria-label="Notifications" className="relative rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
                  <BellIcon className="h-5 w-5" />
                  {unreadCount > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-negative)] px-1 text-[10px] font-bold text-white">{unreadCount > 99 ? '99+' : unreadCount}</span>}
                </button>
                {notifOpen && (
                  <div className="absolute right-0 mt-2 w-[calc(100vw-1.5rem)] max-w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg">
                    <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"><p className="text-sm font-semibold text-[var(--color-ink)]">Notifications</p><button onClick={handleMarkAllRead} className="text-xs font-medium text-[var(--color-primary)] hover:underline">Mark all read</button></div>
                    <div className="max-h-80 overflow-y-auto">
                      {notifications.length === 0 ? <p className="px-4 py-8 text-center text-sm text-[var(--color-muted)]">No notifications</p> : notifications.map((n) => (
                        <div key={n.id} className={`border-b border-[var(--color-border)] px-4 py-3 last:border-0 ${n.is_read ? '' : 'bg-[var(--color-primary-soft)]'}`}><p className="text-sm font-medium text-[var(--color-ink)]">{n.title}</p>{n.message && <p className="mt-0.5 text-xs text-[var(--color-muted)]">{n.message}</p>}</div>
                      ))}
                    </div>
                    <NavLink to="/app/notifications" onClick={() => setNotifOpen(false)} className="block border-t border-[var(--color-border)] px-4 py-2 text-center text-sm font-medium text-[var(--color-primary)] hover:bg-[var(--color-canvas)]">View all</NavLink>
                  </div>
                )}
              </div>
              <div className="relative" ref={userMenuRef}>
                <button onClick={() => setUserMenuOpen((prev) => !prev)} className="flex items-center gap-2 rounded-full bg-[var(--color-primary-soft)] px-2 py-1 pr-1 text-sm font-semibold text-[var(--color-primary-dark)]" aria-label="User menu">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-bold text-white">{initials}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3 w-3"><path d="M6 9l6 6 6-6" /></svg>
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2 shadow-lg">
                    <div className="px-4 py-3"><p className="text-sm font-semibold text-[var(--color-ink)]">{user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}</p><p className="mt-0.5 text-xs text-[var(--color-muted)]">{user?.email || ''}</p></div>
                    <div className="border-t border-[var(--color-border)]" />
                    <NavLink to="/app/profile" onClick={() => setUserMenuOpen(false)} className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]">Profile</NavLink>
                    <button onClick={handleLogout} className="block w-full px-4 py-2 text-left text-sm text-[var(--color-negative)] hover:bg-[var(--color-canvas)]">Logout</button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-1 py-1 sm:px-2 sm:py-2 lg:px-1">{children}</main>
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
