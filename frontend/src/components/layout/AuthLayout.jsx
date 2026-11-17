import { useRef } from 'react'
import Footer from './Footer.jsx'
import AmbientBackground from '../../motion/AmbientBackground.jsx'
import { gsap, useGSAP, prefersReducedMotion, EASE } from '../../motion/gsap.js'

/** Centered card shell used by Login, Register, and OTP Verification. */
export default function AuthLayout({ eyebrow, title, subtitle, children }) {
  const root = useRef(null)
  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.timeline({ defaults: { ease: EASE } })
      .from('.auth-logo', { autoAlpha: 0, y: -20, duration: 0.8 })
      .from('.auth-card', { autoAlpha: 0, y: 40, scale: 0.97, duration: 1 }, 0.1)
      .from('.auth-card > *', { autoAlpha: 0, y: 16, stagger: 0.08, duration: 0.7 }, 0.4)
  }, { scope: root })
  return (
    <div ref={root} className="relative flex min-h-screen flex-col overflow-hidden bg-[var(--color-canvas)]">
      <AmbientBackground />
      <div className="relative z-10 flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="auth-logo mb-8 flex items-center justify-center gap-2">
            <span className="relative inline-flex h-2.5 w-2.5 text-[var(--color-positive)]">
              <span className="pulse-ring absolute inset-0" />
              <span className="relative inline-flex h-full w-full rounded-full bg-current" />
            </span>
            <span className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
              AGSuite ERP
            </span>
          </div>

          <div className="auth-card rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-xl shadow-indigo-500/5">
            {eyebrow && (
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--color-primary)]">
                {eyebrow}
              </p>
            )}
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              {title}
            </h1>
            {subtitle && <p className="mt-1.5 text-sm text-[var(--color-muted)]">{subtitle}</p>}
            <div className="mt-6">{children}</div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
