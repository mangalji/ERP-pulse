import axios from 'axios'
import { API_BASE } from '../utils/constants.js'
import { getAccessToken } from '../utils/token.js'

/**
 * Axios instance configured for dual-mode JWT auth:
 *
 * 1. Authorization header (primary for cross-domain — Vercel frontend →
 *    Render backend). Access token is stored in a JS variable, not
 *    localStorage, so XSS can't steal it.
 * 2. httpOnly cookie (fallback for same-origin requests). The browser
 *    sends it automatically when withCredentials is true.
 */
export const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Send httpOnly cookies when on same origin
})

// Inject the in-memory access token as an Authorization header on every request.
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Token refresh interceptor ──────────────────────────────────────
let isRefreshing = false
let pendingRequests = []

const resolvePending = (error) => {
  pendingRequests.forEach((cb) => cb(error))
  pendingRequests = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (!original || original._retry) return Promise.reject(error)

    const isAuthEndpoint = original.url.includes('/auth/')
    const is401 = error.response?.status === 401

    // Attach the backend's error response so unwrap-like logic works
    if (error.response?.data) {
      error.payload = error.response.data
    }

    if (!is401 || isAuthEndpoint) return Promise.reject(error)

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push((err) => {
          if (err) reject(err)
          else resolve(apiClient(original))
        })
      })
    }

    isRefreshing = true
    original._retry = true

    try {
      // Try cookie-based refresh first (same-origin), fall back to
      // sending the refresh token in the request body (cross-domain).
      const { default: authApi } = await import('../services/auth.js')
      const res = await authApi.refreshToken()
      const newAccess = res.access
      if (newAccess) {
        const { setAccessToken } = await import('../utils/token.js')
        setAccessToken(newAccess)
        original.headers.Authorization = `Bearer ${newAccess}`
      }
      resolvePending(null)
      return apiClient(original)
    } catch (refreshError) {
      const { clearAccessToken } = await import('../utils/token.js')
      clearAccessToken()
      resolvePending(refreshError)
      window.location.href = '/login'
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export const unwrap = (response) => {
  const { success, data, message } = response.data
  if (success) return data
  const err = new Error(message || 'Request failed')
  err.status = response.status
  err.payload = response.data
  throw err
}

export default apiClient
