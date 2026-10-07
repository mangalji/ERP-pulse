export default function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-lg border border-[var(--color-border)] bg-white ${className}`} aria-hidden="true" />
}
