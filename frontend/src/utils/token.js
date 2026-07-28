/**
 * In-memory JWT token storage.
 *
 * Access token is stored in a JavaScript variable (not localStorage), so it's
 * safe from XSS — no JS-injected script can read a module-closure variable.
 *
 * On page refresh the variable resets to null -> user sees login page ->
 * logs in again. This is intentional: short-lived access tokens (15 min)
 * with no persistent storage is more secure than a long-lived refresh
 * token in localStorage.
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
