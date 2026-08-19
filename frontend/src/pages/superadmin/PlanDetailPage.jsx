import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import { superadminApi } from '../../services/superadmin.js'

export default function PlanDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editOpen, setEditOpen] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)

  const loadPlan = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await superadminApi.getPlan(id)
      setPlan(data)
      setEditForm({
        name: data.name,
        description: data.description,
        price: data.price,
        validity_days: data.validity_days,
      })
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load plan')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadPlan()
  }, [loadPlan])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await superadminApi.updatePlan(id, editForm)
      setPlan(updated)
      setEditOpen(false)
    } catch (err) {
      alert(err.payload?.message || err.message || 'Failed to update plan')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <AdminLayout title="Plan" breadcrumb="Plan">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </AdminLayout>
    )
  }

  if (error) {
    return (
      <AdminLayout title="Plan" breadcrumb="Plan">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error}</p>
        </Card>
      </AdminLayout>
    )
  }

  if (!plan) return null

  return (
    <AdminLayout title={plan.name} breadcrumb="Plan Detail">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/admin/plans')}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Plans</span>
        </div>

        <PageHeader
          title={plan.name}
          subtitle={plan.description}
          actions={
            <div className="flex gap-2">
              <Button size="sm" intent="secondary" onClick={() => navigate(`/admin/plans`)}>
                Back to Plans
              </Button>
              <Button size="sm" onClick={() => setEditOpen(true)}>
                Edit Plan
              </Button>
            </div>
          }
        />

        <InfoCard
          title="Basic Information"
          items={[
            { label: 'Plan Name', value: plan.name },
            { label: 'Description', value: plan.description || '—' },
            { label: 'Status', value: <StatusBadge status={plan.status} /> },
            { label: 'Created Date', value: plan.created_at ? new Date(plan.created_at).toLocaleDateString() : '—' },
            { label: 'Updated Date', value: plan.updated_at ? new Date(plan.updated_at).toLocaleDateString() : '—' },
          ]}
        />

        <InfoCard
          title="Pricing"
          items={[
            { label: 'Price', value: `₹${Number(plan.price || 0).toFixed(2)}` },
            { label: 'Validity', value: `${plan.validity_days ?? 30} days` },
          ]}
        />

        {editOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40" onClick={() => setEditOpen(false)} />
            <div className="relative w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Edit Plan
              </h3>
              <div className="mt-4 flex flex-col gap-4">
                <Input label="Plan Name" value={editForm.name || ''} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                <Input label="Description" value={editForm.description || ''} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
                <Input label="Price (₹)" type="number" value={editForm.price || ''} onChange={(e) => setEditForm({ ...editForm, price: e.target.value })} />
                <Input label="Validity (days)" type="number" value={editForm.validity_days || ''} onChange={(e) => setEditForm({ ...editForm, validity_days: e.target.value })} />
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button intent="secondary" size="sm" onClick={() => setEditOpen(false)}>Cancel</Button>
                <Button size="sm" onClick={handleSave} isLoading={saving}>Save Changes</Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  )
}
