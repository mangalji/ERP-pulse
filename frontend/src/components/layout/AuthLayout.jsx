/** Centered card shell used by Login, Register, and OTP Verification. */
export default function AuthLayout({ eyebrow, title, subtitle, children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-canvas)] px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-2">
          <span className="relative inline-flex h-2.5 w-2.5 text-[var(--color-positive)]">
            <span className="pulse-ring absolute inset-0" />
            <span className="relative inline-flex h-full w-full rounded-full bg-current" />
          </span>
          <span className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
            ERP Pulse
          </span>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-sm">
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
  )
}
