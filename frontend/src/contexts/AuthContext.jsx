import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../services/auth.js'
import { getAccessToken, getRefreshToken, clearTokens, setTokens } from '../utils/constants.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [netSuiteConnected, setNetSuiteConnected] = useState(false)

  const bootstrap = async () => {
    const token = getAccessToken()
    if (!token) {
      setIsLoading(false)
      return
    }
    try {
      const data = await authApi.me()
      setUser(data)
      setNetSuiteConnected(Boolean(data.netsuite_connected))
    } catch {
      clearTokens()
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
    const { access, refresh, user: userData } = res
    setTokens(access, refresh)
    setUser(userData)
    setNetSuiteConnected(Boolean(userData.netsuite_connected))
    return userData
  }

  const resendLoginOtp = async (email) => {
    setError(null)
    const res = await authApi.resendLoginOtp(email)
    return res
  }

  const register = async (email, password, confirmPassword) => {
    setError(null)
    const res = await authApi.requestRegisterOtp(email, password, confirmPassword)
    return { email: res.email }
  }

  const verifyRegister = async (email, otpCode) => {
    setError(null)
    const res = await authApi.verifyRegisterOtp(email, otpCode)
    return res
  }

  const completeProfile = async (registrationToken, firstName, lastName, mobileNumber) => {
    setError(null)
    const res = await authApi.completeProfile(registrationToken, firstName, lastName, mobileNumber)
    return res
  }

  const resendRegisterOtp = async (email) => {
    setError(null)
    const res = await authApi.resendRegisterOtp(email)
    return res
  }

  const logout = async () => {
    const refresh = getRefreshToken()
    try {
      if (refresh) await authApi.logout(refresh)
    } finally {
      clearTokens()
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
