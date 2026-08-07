import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, isSuperAdmin, isLoading } = useAuth()
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

  return children
}
