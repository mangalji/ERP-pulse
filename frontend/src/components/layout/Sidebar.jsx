import { NavLink } from 'react-router-dom'
import PulseIndicator from '../ui/PulseIndicator.jsx'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { to: '/connect-netsuite', label: 'Connect NetSuite', icon: PlugIcon },
  { to: '/ai-assistant', label: 'AI Assistant', icon: SparkleIcon },
  { to: '/customers', label: 'Customers', icon: CustomersIcon },
  { to: '/employees', label: 'Employees', icon: EmployeesIcon },
  { to: '/vendors', label: 'Vendors', icon: VendorsIcon },
  { to: '/inventory', label: 'Inventory', icon: InventoryIcon },
  { to: '/reports', label: 'Reports', icon: ReportIcon },
  { to: '/history', label: 'History', icon: ClockIcon },
  { to: '/settings', label: 'Settings', icon: GearIcon },
]

export default function Sidebar({ open, onClose }) {
  return (
    <>
      {open && (
        <button
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-[var(--color-sidebar)] px-4 py-6
          transition-transform lg:static lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="mb-8 flex items-center gap-2 px-2">
          <PulseIndicator state="connected" size="lg" />
          <span className="font-[var(--font-display)] text-lg font-semibold text-white">ERP Pulse</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
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
        </nav>

        <div className="rounded-lg bg-[var(--color-sidebar-soft)] p-3 text-xs text-[var(--color-sidebar-ink)]">
          Source of truth: <span className="text-[var(--color-netsuite)]">NetSuite</span>. ERP Pulse never
          stores your business records locally.
        </div>
      </aside>
    </>
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
function PlugIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M9 3v4M15 3v4M7 7h10l-1 5a4 4 0 0 1-8 0L7 7Z" />
      <path d="M12 16v5" />
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
function CustomersIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="9" cy="6" r="2.5" />
      <circle cx="17" cy="6" r="2.5" />
      <path d="M2 18c0-3.3 3.6-6 7-6s7 2.7 7 6" />
      <path d="M15 18c0-3.3 3.6-6 7-6s1.5 2.7 1.5 6" />
    </svg>
  )
}
function EmployeesIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <rect x="4" y="3" width="16" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  )
}
function VendorsIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M3 21h18" />
      <path d="M5 21V7l7-4 7 4v14" />
      <path d="M9 21v-6h6v6" />
      <path d="M9 9h.01M15 9h.01M9 13h.01M15 13h.01" />
    </svg>
  )
}
function InventoryIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M21 8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v7a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 15z" />
      <path d="M3.5 8.5 12 13l8.5-4.5" />
      <path d="M12 13V21" />
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
function ClockIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
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
