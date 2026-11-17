import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion, EASE } from './gsap.js'

/**
 * Staggered entrance for every `[data-reveal]` element inside the ref'd
 * container. Re-runs when `deps` change (e.g. after data loads).
 */
export function useReveal(deps = [], { y = 18, stagger = 0.06, delay = 0 } = {}) {
  const scope = useRef(null)
  useGSAP(
    () => {
      const items = gsap.utils.toArray('[data-reveal]', scope.current)
      if (!items.length || prefersReducedMotion()) return
      gsap.fromTo(
        items,
        { autoAlpha: 0, y },
        { autoAlpha: 1, y: 0, duration: 0.7, ease: EASE, stagger, delay, clearProps: 'transform,opacity,visibility' },
      )
    },
    { scope, dependencies: deps },
  )
  return scope
}
