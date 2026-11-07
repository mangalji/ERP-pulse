import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import { isCompanyAdminUser } from '../utils/netsuiteErrors.js'

function AccessDenied() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)] p-6">
      <section className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-[var(--color-ink)]">Access restricted</h1>
        <p className="mt-3 text-sm text-[var(--color-muted)]">
          You do not have permission to access Email Integration. Please contact your Company Admin.
        </p>
        <Link
          to="/app"
          className="mt-6 inline-flex rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Back to dashboard
        </Link>
      </section>
    </main>
  )
}

export default function ProtectedRoute({ children, requiredRole }) {
  const { user, isAuthenticated, isSuperAdmin, isLoading, clientContextLoading } = useAuth()
  const location = useLocation()

  if (
    isLoading ||
    (['client', 'companyAdmin'].includes(requiredRole) && clientContextLoading)
  ) {
     return (
        <div className="flex min-h-screen items-center justify-center">
          <span className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--color-border)] border-t-[var(--color-primary)]" />
        </div>
      )
    }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  if (requiredRole === 'admin' && !isSuperAdmin) {
    return <Navigate to="/app" replace />
  }

  if (requiredRole === 'client' && isSuperAdmin) {
    return <Navigate to="/admin" replace />
  }

  if (requiredRole === 'companyAdmin') {
    if (isSuperAdmin) {
      return <Navigate to="/admin" replace />
    }
    if (!isCompanyAdminUser(user)) {
      return <AccessDenied />
    }
  }

  return children
}
