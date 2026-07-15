import { useState, useEffect } from 'react'
import Button from '../ui/Button.jsx'
import Skeleton from '../ui/Skeleton.jsx'
import ErrorState from '../ui/ErrorState.jsx'
import Card from '../ui/Card.jsx'

export default function EntityDetail({ fetchFn, recordId, title, fields, onBack }) {
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!recordId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchFn(recordId)
      .then((data) => {
        if (!cancelled) setRecord(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.payload?.message || err.message || 'Failed to load record')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchFn, recordId])

  if (!recordId) {
    return (
      <Card className="p-6">
        <p className="text-sm text-[var(--color-muted)]">Select a record to view details.</p>
      </Card>
    )
  }

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex flex-col gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-6">
        <ErrorState message={error} onRetry={() => fetchFn(recordId).then(setRecord).catch(() => {})} />
      </Card>
    )
  }

  if (!record) return null

  const renderValue = (value) => {
    if (value && typeof value === 'object' && value.name) {
      return value.name
    }
    if (Array.isArray(value)) {
      return `${value.length} item${value.length !== 1 ? 's' : ''}`
    }
    if (value === null || value === undefined) return '--'
    return String(value)
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
          {title || 'Record Details'}
        </h3>
        {onBack && (
          <Button intent="secondary" size="sm" onClick={onBack}>
            Back
          </Button>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {fields.map((field) => (
          <div key={field.key}>
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted)]">
              {field.label}
            </p>
            <p className="mt-1 text-sm text-[var(--color-ink)]">{renderValue(record[field.key])}</p>
          </div>
        ))}
      </div>
    </Card>
  )
}
