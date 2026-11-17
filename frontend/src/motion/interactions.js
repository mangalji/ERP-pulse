import { gsap, prefersReducedMotion } from './gsap.js'

/** Lift + cursor-follow glow (updates throttled to one per frame). */
export function spotlightHandlers() {
  if (prefersReducedMotion()) return {}
  let raf = 0
  return {
    onMouseEnter: (e) => gsap.to(e.currentTarget, { y: -3, duration: 0.35, ease: 'power2.out', overwrite: 'auto' }),
    onMouseMove: (e) => {
      const el = e.currentTarget
      const { clientX, clientY } = e
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = 0
        const r = el.getBoundingClientRect()
        el.style.setProperty('--mx', `${clientX - r.left}px`)
        el.style.setProperty('--my', `${clientY - r.top}px`)
      })
    },
    onMouseLeave: (e) => gsap.to(e.currentTarget, { y: 0, duration: 0.5, ease: 'power3.out', overwrite: 'auto' }),
  }
}

/** Gentle magnetic pull + press squish for buttons. */
export function buttonHandlers() {
  if (prefersReducedMotion()) return {}
  return {
    onMouseMove: (e) => {
      const el = e.currentTarget
      if (el.disabled) return
      const r = el.getBoundingClientRect()
      gsap.to(el, { x: (e.clientX - r.left - r.width / 2) * 0.1, y: (e.clientY - r.top - r.height / 2) * 0.15, duration: 0.4, overwrite: 'auto' })
    },
    onMouseLeave: (e) => gsap.to(e.currentTarget, { x: 0, y: 0, scale: 1, duration: 0.5, ease: 'power3.out', overwrite: 'auto' }),
    onMouseDown: (e) => !e.currentTarget.disabled && gsap.to(e.currentTarget, { scale: 0.96, duration: 0.1, overwrite: 'auto' }),
    onMouseUp: (e) => gsap.to(e.currentTarget, { scale: 1, duration: 0.35, ease: 'back.out(2)', overwrite: 'auto' }),
  }
}
