import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

/** Gates authenticated-only pages using the UI-only AuthContext state. */
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}
