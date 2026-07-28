import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../services/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [netSuiteConnected, setNetSuiteConnected] = useState(false)

  /**
   * Bootstrap: check if the user is already logged in by calling
   * /auth/me/. The browser sends the httpOnly access_token cookie
   * automatically (withCredentials: true on apiClient). No localStorage
   * reads needed.
   *
   * If the cookie is missing or expired, /auth/me/ returns 401 and we
   * clear the user state — the user sees the login page.
   */
  const bootstrap = async () => {
    try {
      const data = await authApi.me()
      setUser(data)
      setNetSuiteConnected(Boolean(data.netsuite_connected))
    } catch {
      // No valid access_token cookie — user is not logged in. This is
      // expected on first visit or after cookie expiry.
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    bootstrap()
  }, [])

  const login = async (email, password) => {
    setError(null)
    const res = await authApi.requestLoginOtp(email, password)
    return { email: res.email }
  }

  const verifyLogin = async (email, otpCode) => {
    setError(null)
    const res = await authApi.verifyLoginOtp(email, otpCode)
    // Backend sets httpOnly cookies for access_token and refresh_token.
    // The `res` also contains the user object — use it directly.
    const { user: userData } = res
    setUser(userData)
    setNetSuiteConnected(Boolean(userData.netsuite_connected))
    return userData
  }

  const resendLoginOtp = async (email) => {
    setError(null)
    return await authApi.resendLoginOtp(email)
  }

  const register = async (email, password, confirmPassword) => {
    setError(null)
    const res = await authApi.requestRegisterOtp(email, password, confirmPassword)
    return { email: res.email }
  }

  const verifyRegister = async (email, otpCode) => {
    setError(null)
    return await authApi.verifyRegisterOtp(email, otpCode)
  }

  const completeProfile = async (registrationToken, firstName, lastName, mobileNumber) => {
    setError(null)
    return await authApi.completeProfile(registrationToken, firstName, lastName, mobileNumber)
  }

  const resendRegisterOtp = async (email) => {
    setError(null)
    return await authApi.resendRegisterOtp(email)
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

  const profileUpdate = async (otpCode, profileData) => {
    setError(null)
    const res = await authApi.profileUpdate(otpCode, profileData)
    setUser(res)
    return res
  }

  const logout = async () => {
    try {
      // Backend clears the httpOnly cookies and blacklists the refresh
      // token. The refresh_token cookie is sent automatically.
      await authApi.logout()
    } finally {
      setUser(null)
      setNetSuiteConnected(false)
    }
  }

  const connectNetSuite = () => setNetSuiteConnected(true)
  const disconnectNetSuite = () => setNetSuiteConnected(false)

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      error,
      login,
      verifyLogin,
      resendLoginOtp,
      register,
      verifyRegister,
      completeProfile,
      resendRegisterOtp,
      forgotPassword,
      resetPassword,
      profileSendOtp,
      profileUpdate,
      logout,
      netSuiteConnected,
      connectNetSuite,
      disconnectNetSuite,
    }),
    [user, isLoading, error, netSuiteConnected],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
