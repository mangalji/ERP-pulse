import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(useGSAP, ScrollTrigger)

// One easing language for the whole product: fast out, soft landing.
export const EASE = 'expo.out'
export const EASE_SOFT = 'power3.out'

gsap.defaults({ ease: EASE_SOFT, duration: 0.6 })

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export { gsap, useGSAP, ScrollTrigger }

// Runs a shell intro only once per browser tab per key (e.g. 'admin-shell'),
// so navigating between pages that remount the same layout doesn't replay it.
const playedShells = new Set()
export function hasPlayedShell(key) {
  return playedShells.has(key)
}
export function markShellPlayed(key) {
  playedShells.add(key)
}
