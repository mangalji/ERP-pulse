import Button from './Button.jsx'

export default function PaginationControls({ currentPage, totalPages, onPrevious, onNext }) {
  if (totalPages <= 1) return null

  return (
    <div className="mt-4 flex items-center justify-between">
      <Button intent="secondary" size="sm" disabled={currentPage <= 1} onClick={onPrevious}>
        Previous
      </Button>
      <span className="text-sm text-[var(--color-muted)]">
        Page {currentPage} of {totalPages}
      </span>
      <Button intent="secondary" size="sm" disabled={currentPage >= totalPages} onClick={onNext}>
        Next
      </Button>
    </div>
  )
}
