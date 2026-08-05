import { useEffect, useState } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import StatusBadge from '../../components/reports-engine/StatusBadge.jsx'
import ScheduleDialog from '../../components/reports-engine/ScheduleDialog.jsx'
import { REPORT_TYPE_LABEL, formatDate } from '../../components/reports-engine/constants.js'
import { reportsEngineApi } from '../../services/reportsEngine.js'

const FREQUENCY_TONE = {
  DAILY: 'primary',
  WEEKLY: 'positive',
  MONTHLY: 'netsuite',
  QUARTERLY: 'neutral',
  YEARLY: 'neutral',
}

export default function ScheduledReportsPage() {
  const [schedules, setSchedules] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await reportsEngineApi.schedules.list({ limit: 100, offset: 0 })
      setSchedules(res?.results ?? res ?? [])
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load schedules')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async (data) => {
    try {
      if (editing) {
        await reportsEngineApi.schedules.update(editing.id, data)
      } else {
        await reportsEngineApi.schedules.create(data)
      }
      setDialogOpen(false)
      setEditing(null)
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to save schedule')
    }
  }

  const toggleActive = async (schedule) => {
    try {
      if (schedule.is_active) {
        await reportsEngineApi.schedules.deactivate(schedule.id)
      } else {
        await reportsEngineApi.schedules.activate(schedule.id)
      }
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to update schedule')
    }
  }

  const runNow = async (schedule) => {
    try {
      await reportsEngineApi.schedules.runNow(schedule.id)
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to run schedule')
    }
  }

  const remove = async (schedule) => {
    if (!window.confirm(`Delete schedule "${schedule.name}"?`)) return
    try {
      await reportsEngineApi.schedules.remove(schedule.id)
      load()
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to delete schedule')
    }
  }

  return (
    <ClientLayout title="Reports" breadcrumb="Scheduled Reports">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Scheduled Reports
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Automate report generation on a recurring basis.
            </p>
          </div>
          <Button onClick={() => { setEditing(null); setDialogOpen(true) }}>New Schedule</Button>
        </div>

        {error && (
          <div className="rounded-lg border border-[var(--color-negative)] bg-[var(--color-negative-soft)] px-4 py-3 text-sm text-[var(--color-negative)]">
            {error}
          </div>
        )}

        <Card className="p-5">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : schedules.length === 0 ? (
            <EmptyState
              title="No schedules yet"
              description="Create a schedule to automatically run reports."
              actionLabel="New Schedule"
              action={() => { setEditing(null); setDialogOpen(true) }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    {['Name', 'Report Type', 'Frequency', 'Format', 'Next Run', 'Status', 'Actions'].map((h) => (
                      <th key={h} className="px-3 py-2.5 whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr key={s.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-canvas)]">
                      <td className="px-3 py-2.5 font-medium text-[var(--color-ink)]">{s.name}</td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                        {REPORT_TYPE_LABEL[s.report_type] || s.report_type}
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <StatusBadge status={s.frequency} />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">{s.format}</td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-[var(--color-ink-soft)]">
                        {formatDate(s.next_run_at)}
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <StatusBadge status={s.is_active ? 'PROCESSING' : 'EXPIRED'} />
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <button onClick={() => runNow(s)} className="rounded-lg px-2 py-1 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
                            Run now
                          </button>
                          <button onClick={() => toggleActive(s)} className={`rounded-lg px-2 py-1 text-xs font-medium ${s.is_active ? 'text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]' : 'text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]'}`}>
                            {s.is_active ? 'Pause' : 'Resume'}
                          </button>
                          <button onClick={() => { setEditing(s); setDialogOpen(true) }} className="rounded-lg px-2 py-1 text-xs font-medium text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
                            Edit
                          </button>
                          <button onClick={() => remove(s)} className="rounded-lg px-2 py-1 text-xs font-medium text-[var(--color-negative)] hover:bg-[var(--color-negative-soft)]">
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <ScheduleDialog
          open={dialogOpen}
          schedule={editing}
          onClose={() => { setDialogOpen(false); setEditing(null) }}
          onSave={handleSave}
        />
      </div>
    </ClientLayout>
  )
}
