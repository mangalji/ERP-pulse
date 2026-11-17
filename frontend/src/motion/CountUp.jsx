import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from './gsap.js'

/** Animates a number from 0 to `value`; non-numeric values render as-is. */
export default function CountUp({ value, duration = 1.4 }) {
  const ref = useRef(null)
  const raw = typeof value === 'string' ? Number(value.replace(/,/g, '')) : value
  const isNum = Number.isFinite(raw) && value !== '' && value !== null
  const hasDecimals = isNum && !Number.isInteger(raw)

  useGSAP(
    () => {
      if (!isNum || !ref.current || prefersReducedMotion()) return
      const o = { n: 0 }
      gsap.to(o, {
        n: raw,
        duration,
        ease: 'power3.out',
        onUpdate: () => {
          if (ref.current)
            ref.current.textContent = hasDecimals ? o.n.toFixed(2) : Math.round(o.n).toLocaleString()
        },
      })
    },
    { dependencies: [raw] },
  )

  return <span ref={ref}>{isNum ? (hasDecimals ? raw.toFixed(2) : raw.toLocaleString()) : (value ?? '--')}</span>
}
