import axios from 'axios'
import { API_BASE, getAccessToken, getRefreshToken, setTokens, clearTokens } from '../utils/constants.js'

export const apiClient = axios.create({ baseURL: API_BASE })

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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
    if (!original || !original.url) return Promise.reject(error)

    const isAuthEndpoint = original.url.includes('/auth/')
    const is401 = error.response?.status === 401

    if (!is401 || isAuthEndpoint) return Promise.reject(error)

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push((err) => (err ? reject(err) : resolve(apiClient(original))))
      })
    }

    isRefreshing = true
    const refresh = getRefreshToken()
    if (!refresh) {
      clearTokens()
      return Promise.reject(error)
    }

    try {
      const res = await axios.post(`${API_BASE}/auth/token/refresh/`, { refresh })
      const { access, refresh: newRefresh } = res.data.data
      setTokens(access, newRefresh)
      original.headers.Authorization = `Bearer ${access}`
      resolvePending(null)
      return apiClient(original)
    } catch (refreshError) {
      clearTokens()
      resolvePending(refreshError)
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
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
