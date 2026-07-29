import { useState, useEffect, useMemo, useCallback } from 'react'
import Input from '../ui/Input.jsx'
import Button from '../ui/Button.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import ErrorState from '../ui/ErrorState.jsx'

const PAGE_SIZE = 50

export default function EntityList({
  fetchFn,
  columns,
  searchPlaceholder = 'Search...',
  title,
  rowKey = 'id',
  onRowClick,
}) {
  const [records, setRecords] = useState([])
  const [totalResults, setTotalResults] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  const loadPage = useCallback(
    (pageOffset) => {
      setLoading(true)
      setError(null)
      return fetchFn({ offset: pageOffset, limit: PAGE_SIZE })
        .then((res) => {
          setRecords(res.results || [])
          setTotalResults(res.count || 0)
          setOffset(pageOffset)
        })
        .catch((err) => {
          setError(err.payload?.message || err.message || 'Failed to load records')
        })
        .finally(() => {
          setLoading(false)
        })
    },
    [fetchFn]
  )

  useEffect(() => {
    loadPage(0)
  }, [loadPage])

  const filteredRecords = useMemo(() => {
    if (!searchQuery.trim()) return records
    const q = searchQuery.toLowerCase()
    return records.filter((record) =>
      Object.values(record).some((v) => String(v).toLowerCase().includes(q))
    )
  }, [records, searchQuery])

  const isSearching = searchQuery.trim().length > 0
  const showingFrom = offset + 1
  const showingTo = Math.min(offset + records.length, totalResults)
  const hasNextPage = offset + records.length < totalResults && !isSearching

  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value)
  }

  const renderCell = (record, column) => {
    const value = record[column.key]
    if (column.render) {
      return column.render(value, record)
    }
    if (value && typeof value === 'object' && value.name) {
      return value.name
    }
    return value != null ? String(value) : '--'
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
          {title}
        </h2>
        <Input
          type="search"
          placeholder={searchPlaceholder}
          value={searchQuery}
          onChange={handleSearchChange}
          className="sm:max-w-xs"
        />
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => loadPage(offset)} />
      ) : (
        <>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center border-b border-[var(--color-border)] bg-[var(--color-canvas)]">
              {columns.map((column, idx) => (
                <div
                  key={column.key}
                  className={`${column.className || 'flex-1'} px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]`}
                >
                  {column.label}
                </div>
              ))}
            </div>

            {loading ? (
              <div className="flex flex-col">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className={`flex items-center px-4 py-3 ${
                      i !== 4 ? 'border-b border-[var(--color-border)]' : ''
                    }`}
                  >
                    {columns.map((column) => (
                      <div key={column.key} className={column.className || 'flex-1'}>
                        <Skeleton className="h-4 w-full max-w-[120px]" />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : filteredRecords.length === 0 ? (
              <EmptyState
                title={isSearching ? 'No matches found' : 'No records found'}
                description={
                  isSearching
                    ? 'Try adjusting your search query.'
                    : 'There are no records to display yet.'
                }
              />
            ) : (
              <div className="flex flex-col">
                {filteredRecords.map((record) => (
                  <button
                    key={record[rowKey] || record.id}
                    onClick={() => onRowClick?.(record)}
                    className={`flex items-center px-4 py-3 text-sm text-left transition-colors hover:bg-[var(--color-canvas)] ${
                      columns.length > 1 ? 'border-b border-[var(--color-border)] last:border-b-0' : ''
                    }`}
                  >
                    {columns.map((column) => (
                      <div key={column.key} className={`${column.className || 'flex-1'}`}>
                        {renderCell(record, column)}
                      </div>
                    ))}
                  </button>
                ))}
              </div>
            )}
          </div>

          {!loading && records.length > 0 && (
            <div className="flex items-center justify-between text-xs text-[var(--color-muted)]">
              <span>
                {isSearching
                  ? `Showing ${filteredRecords.length} of ${records.length} records`
                  : `Showing ${showingFrom}–${showingTo} of ${totalResults}`}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  intent="secondary"
                  disabled={offset === 0 || isSearching}
                  onClick={() => loadPage(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  intent="secondary"
                  disabled={!hasNextPage}
                  onClick={() => loadPage(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
