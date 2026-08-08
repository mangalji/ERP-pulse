import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

/**
 * ModuleProtectedRoute — extends ProtectedRoute with module + permission checks.
 *
 * Flow:
 *   1. Auth check (same as ProtectedRoute)
 *   2. Module check — company must have the module enabled
 *   3. Permission check — the user's role must grant the required permission code
 *
 * Super Admin bypasses all module/permission gates.
 */
export default function ModuleProtectedRoute({ children, requiredRole, requiredModule, requiredPermission }) {
  const { isAuthenticated, isSuperAdmin, isLoading, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
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

  // Super Admin bypasses module + permission gates
  if (isSuperAdmin) {
    return children
  }

  // MODULE CHECK
  if (requiredModule) {
    const enabledModules = user?.modules || []
    const hasModule = enabledModules.some((m) => m.module_code === requiredModule)
    if (!hasModule) {
      return (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Access Denied
            </h1>
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              Module &ldquo;{requiredModule}&rdquo; is not included in your subscription.
            </p>
          </div>
        </div>
      )
    }
  }

  // PERMISSION CHECK
  if (requiredPermission) {
    const permissions = user?.permissions || []
    const hasPermission = permissions.includes(requiredPermission)
    if (!hasPermission) {
      return (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Access Denied
            </h1>
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              You do not have permission to access this page.
            </p>
          </div>
        </div>
      )
    }
  }

  return children
}
