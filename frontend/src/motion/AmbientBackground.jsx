import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from './gsap.js'

const blob = (color, opacity) => ({
  background: `radial-gradient(circle at center, ${color} 0%, transparent 65%)`,
  opacity,
  willChange: 'transform',
})

/** Slow-drifting gradient glows. No blur filters, transform-only = cheap on the GPU. */
export default function AmbientBackground() {
  const ref = useRef(null)
  useGSAP(
    () => {
      if (prefersReducedMotion()) return
      gsap.utils.toArray('.aurora-blob', ref.current).forEach((el, i) => {
        gsap.to(el, {
          x: gsap.utils.random(-60, 60), y: gsap.utils.random(-40, 40),
          duration: gsap.utils.random(14, 20), ease: 'sine.inOut', repeat: -1, yoyo: true, delay: i * -4, force3D: true,
        })
      })
    },
    { scope: ref },
  )
  return (
    <div ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="aurora-blob absolute -left-40 -top-40 h-[32rem] w-[32rem] rounded-full" style={blob('var(--color-primary)', 0.12)} />
      <div className="aurora-blob absolute -right-40 top-1/3 h-[32rem] w-[32rem] rounded-full" style={blob('#06b6d4', 0.09)} />
      <div className="aurora-blob absolute -bottom-40 left-1/3 h-[28rem] w-[28rem] rounded-full" style={blob('#a855f7', 0.09)} />
    </div>
  )
}
