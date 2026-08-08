import { useAuth } from '../../contexts/AuthContext.jsx'

/**
 * Wraps a route and verifies that the user's company has the required
 * module enabled. Falls back to a 403-style "module not included" page
 * instead of redirecting (which would cause redirect loops).
 */
export default function ModuleRequired({ children, moduleCode }) {
  const { user, isSuperAdmin } = useAuth()
  const enabledModules = user?.modules || []

  if (isSuperAdmin) {
    return children
  }

  if (!moduleCode) {
    return children
  }

  const hasModule = enabledModules.some((m) => m.module_code === moduleCode)
  if (!hasModule) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
            Access Denied
          </h1>
          <p className="mt-2 text-sm text-[var(--color-muted)]">
            Module &ldquo;{moduleCode}&rdquo; is not included in your subscription.
          </p>
        </div>
      </div>
    )
  }

  return children
}
