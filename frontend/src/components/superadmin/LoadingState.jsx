import Skeleton from '../ui/Skeleton.jsx'

/**
 * Loading placeholder for tables and lists.
 * Renders a set of skeleton rows while data is being fetched.
 */
export default function LoadingState({ rows = 4 }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}
