import { createContext, useContext, useMemo, useState } from 'react'

/**
 * UI-only auth state for gating routes during frontend development.
 * Holds no tokens and makes no API calls — this task explicitly excludes
 * backend/API integration. Replace with a real auth context once the
 * login/register APIs are wired in.
 */
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [netSuiteConnected, setNetSuiteConnected] = useState(false)

  const value = useMemo(
    () => ({
      isAuthenticated,
      login: () => setIsAuthenticated(true),
      logout: () => setIsAuthenticated(false),
      netSuiteConnected,
      connectNetSuite: () => setNetSuiteConnected(true),
    }),
    [isAuthenticated, netSuiteConnected],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
