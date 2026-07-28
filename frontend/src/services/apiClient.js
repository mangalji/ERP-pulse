import axios from 'axios'
import { API_BASE } from '../utils/constants.js'

/**
 * Axios instance configured for httpOnly cookie-based JWT auth.
 *
 * The browser automatically attaches the access_token and refresh_token
 * httpOnly cookies on every request to the same origin (or sub-origin
 * when withCredentials is set). No localStorage reads, no manual
 * Authorization header injection.
 */
export const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Send httpOnly cookies cross-origin
})

// ── Token refresh interceptor ──────────────────────────────────────
// When a request returns 401, attempt a silent token refresh by calling
// the refresh endpoint (the browser sends the refresh_token cookie
// automatically). On success, retry the original request once.
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
      // The refresh_token cookie is sent automatically with
      // withCredentials: true — no body needed.
      await apiClient.post('/auth/token/refresh/')
      resolvePending(null)
      return apiClient(original)
    } catch (refreshError) {
      // Refresh failed (cookie expired or invalid) — redirect to login.
      // Clear any server-side state by calling logout (cookie will be
      // cleared by the backend).
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
