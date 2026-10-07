import { createContext, useContext, useEffect, useRef, useMemo, useState } from 'react'
import { authApi } from '../services/auth.js'
import { clientApi } from '../services/client.js'
import { setAccessToken, clearAccessToken } from '../utils/token.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [clientContextLoading, setClientContextLoading] = useState(false)
  const [error, setError] = useState(null)
  const [netSuiteConnected, setNetSuiteConnected] = useState(false)
  const clientContextRequestId = useRef(0)
  const bootstrapRequestId = useRef(0)

  const loadClientContext = async (baseUser) => {
    if (baseUser?.is_superadmin || baseUser?.is_staff) {
      setClientContextLoading(false)
      return
    }
    const requestId = ++clientContextRequestId.current
    setClientContextLoading(true)
    if (baseUser?.id) {
      void clientApi.getNavigationMenu(baseUser.id).catch(() => null)
    }
     try {
      const ctx = await clientApi.getMe()

      // Ignore a stale response if the user logged out or another auth flow
      // started while this request was in flight.
      if (requestId !== clientContextRequestId.current) return

      setUser((prev) => ({
        ...prev,
        modules: ctx.modules || [],
        roles: ctx.roles || [],
        permissions: ctx.permissions || [],
        company: ctx.company,
        plan: ctx.plan,
      }))
    } catch {
      // Authentication is already established. A client-context failure must
      // not make the whole application appear logged out.
    } finally {
      if (requestId === clientContextRequestId.current) {
        setClientContextLoading(false)
      }
    }
    }

  /**
   * Bootstrap authentication first, then load client context in the
   * background. Previously /auth/me/ and /client/me/ formed a blocking
   * waterfall, so the entire application waited for both requests before
   * rendering. Authentication is enough to establish the session; module and
   * permission data can safely arrive immediately after that.
   */
  useEffect(() => {
    let cancelled = false
  const requestId = ++bootstrapRequestId.current
  const bootstrap = async () => {
    try {
      const data = await authApi.me()

      if (cancelled || requestId != bootstrapRequestId.current) return

      setUser(data)
      setNetSuiteConnected(Boolean(data.netsuite_connected))
      setIsLoading(false)

      // Do not block the first authenticated render on this second request.     
      void loadClientContext(data)
    } catch {
      if (cancelled) return
      setUser(null)
      setClientContextLoading(false)
      setIsLoading(false)
    }
  }
  void bootstrap()

    return () => {
      cancelled = true
      bootstrapRequestId.current += 1
      clientContextRequestId.current += 1
    }
  }, [])

  const login = async (email, password) => {
    setError(null)
    const res = await authApi.requestLoginOtp(email, password)
    return { email: res.email }
  }

  const verifyLogin = async (email, otpCode) => {
    setError(null)

    bootstrapRequestId.current += 1
    const res = await authApi.verifyLoginOtp(email, otpCode)
    // Store access token in memory (safe from XSS).
    if (res.access) setAccessToken(res.access)
    const { user: userData } = res
    setNetSuiteConnected(Boolean(userData.netsuite_connected))
    setUser(userData)
    setIsLoading(false)

    // Do not make OTP verification wait for the client-context request.
    void loadClientContext(userData)

      return userData
    }

  const resendLoginOtp = async (email) => {
    setError(null)
    return await authApi.resendLoginOtp(email)
  }

  const forgotPassword = async (email) => {
    setError(null)
    return await authApi.forgotPassword(email)
  }

  const resetPassword = async (email, otpCode, password, confirmPassword) => {
    setError(null)
    return await authApi.resetPassword(email, otpCode, password, confirmPassword)
  }

  const profileSendOtp = async () => {
    setError(null)
    return await authApi.profileSendOtp()
  }

  const profileUpdate = async (profileData) => {
  setError(null)

  const res = await authApi.profileUpdate(profileData)
  setUser((prev) => ({ ...prev, ...res }))
  return res
}

  const logout = async () => {
    // Invalidate any in-flight client-context request before changing auth state.
    clientContextRequestId.current += 1
    bootstrapRequestId.current += 1
    try {
      await authApi.logout()
    } finally {
      clearAccessToken()
      setUser(null)
      setClientContextLoading(false)
      setNetSuiteConnected(false)
      setIsLoading(false)
    }
  }

  const connectNetSuite = () => setNetSuiteConnected(true)
  const disconnectNetSuite = () => setNetSuiteConnected(false)

  const isSuperAdmin = Boolean(user?.is_superadmin || user?.is_staff)

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isSuperAdmin,
      isLoading,
      clientContextLoading,
      error,
      login,
      verifyLogin,
      resendLoginOtp,
      forgotPassword,
      resetPassword,
      profileSendOtp,
      profileUpdate,
      logout,
      netSuiteConnected,
      connectNetSuite,
      disconnectNetSuite,
    }),
    [user, isLoading, clientContextLoading, error, netSuiteConnected],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
