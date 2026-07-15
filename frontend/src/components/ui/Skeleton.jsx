export default function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-[var(--color-sidebar-soft)] ${className}`} aria-hidden="true" />
}
