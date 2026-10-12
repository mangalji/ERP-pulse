/**
 * In-memory JWT token storage.
 *
 * Access token is stored in a JavaScript variable (not localStorage), so it's
 * safe from XSS — no JS-injected script can read a module-closure variable.
 *
 * The variable resets to null when a page reloads or a new browser tab opens.
 * The backend's httpOnly access-token cookie can authenticate the initial
 * request; if that token is missing or expired, apiClient refreshes the session
 * using the httpOnly refresh-token cookie. The refresh cookie remains invisible
 * to JavaScript, avoiding token storage in localStorage.
 *
 * The refresh_token httpOnly cookie (set by the backend on login) is the
 * persistent credential. It's used by the token refresh flow and is
 * invisible to JavaScript.
 */

let _accessToken = null

export function getAccessToken() {
  return _accessToken
}

export function setAccessToken(token) {
  _accessToken = token
}

export function clearAccessToken() {
  _accessToken = null
}
