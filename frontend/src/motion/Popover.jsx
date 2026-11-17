import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion, EASE } from './gsap.js'

/** Menu/dropdown surface that springs in; children cascade. Mount = open. */
export default function Popover({ children, className = '' }) {
  const ref = useRef(null)
  useGSAP(
    () => {
      if (prefersReducedMotion()) return
      gsap.fromTo(ref.current, { autoAlpha: 0, y: -8, scale: 0.96, transformOrigin: 'top right' }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.35, ease: EASE })
      gsap.from(ref.current.children, { autoAlpha: 0, y: -6, stagger: 0.04, duration: 0.3, delay: 0.05 })
    },
    { scope: ref },
  )
  return <div ref={ref} className={className}>{children}</div>
}
