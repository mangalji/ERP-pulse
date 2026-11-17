import { useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { gsap, useGSAP, prefersReducedMotion, EASE } from './gsap.js'

/**
 * Wraps page content: on every route change the page fades/slides in and its
 * `[data-reveal]` blocks cascade. Headings and cards animate as a sequence.
 */
export default function PageTransition({ children, className = '' }) {
  const ref = useRef(null)
  const { pathname } = useLocation()

  useGSAP(
    () => {
      if (prefersReducedMotion() || !ref.current) return
      const items = gsap.utils.toArray('[data-reveal]', ref.current).slice(0, 16)
      const targets = items.length ? items : [ref.current]
      gsap.fromTo(
        targets,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.5, ease: EASE, stagger: 0.045, force3D: true, clearProps: 'transform,opacity' },
      )
    },
    { scope: ref, dependencies: [pathname] },
  )

  return <div ref={ref} className={className}>{children}</div>
}
