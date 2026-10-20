import { API_BASE } from './constants.js'

export function getProfilePictureUrl(profilePicture) {
  if (!profilePicture || typeof profilePicture !== 'string') return ''
  if (/^(?:https?:|blob:|data:)/i.test(profilePicture)) return profilePicture

  const apiOrigin = new URL(API_BASE, window.location.origin).origin
  return new URL(profilePicture.startsWith('/') ? profilePicture : `/${profilePicture}`, apiOrigin).toString()
}
