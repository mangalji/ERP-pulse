import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
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
  const [allModules, setAllModules] = useState([])
  const [loadingModules, setLoadingModules] = useState(false)

  const loadPlan = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await superadminApi.getPlan(id)
      setPlan(data)
      setEditForm({
        name: data.name,
        description: data.description,
        monthly_price: data.monthly_price,
        yearly_price: data.yearly_price,
        max_employees: data.max_employees,
        max_ocr_documents: data.max_ocr_documents,
        max_storage_gb: data.max_storage_gb,
        trial_days: data.trial_days,
        ai_credits: data.ai_credits,
        ocr_credits: data.ocr_credits,
        status: data.status,
        enabled_models: (data.enabled_modules || []).map((m) => m.id),
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

  const loadModules = async () => {
    setLoadingModules(true)
    try {
      const modData = await superadminApi.listModules()
      setAllModules(modData.results || modData || [])
    } catch {
      setAllModules([])
    } finally {
      setLoadingModules(false)
    }
  }

  const handleEdit = () => {
    loadModules()
    setEditOpen(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await superadminApi.updatePlan(id, editForm)
      setPlan(updated)
      setEditOpen(false)
    } catch (err) {
      // eslint-disable-next-line no-alert
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

  const enabledModules = plan.enabled_modules || []

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
              <Button size="sm" onClick={() => handleEdit()}>
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
            { label: 'Monthly Price', value: `₹${Number(plan.monthly_price || 0).toFixed(2)}` },
            { label: 'Yearly Price', value: `₹${Number(plan.yearly_price || 0).toFixed(2)}` },
          ]}
        />

        <InfoCard
          title="Limits"
          items={[
            { label: 'Max Employees', value: plan.max_employees ?? 0 },
            { label: 'Max OCR Documents', value: plan.max_ocr_documents ?? 0 },
            { label: 'Max Storage (GB)', value: plan.max_storage_gb ?? 0 },
            { label: 'Trial Days', value: plan.trial_days ?? 0 },
            { label: 'AI Credits', value: plan.ai_credits ?? 0 },
            { label: 'OCR Credits', value: plan.ocr_credits ?? 0 },
          ]}
        />

        <SectionCard
          title="Included Modules"
          subtitle={`${enabledModules.length} module${enabledModules.length !== 1 ? 's' : ''} included`}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {enabledModules.map((mod) => (
              <div
                key={mod.id}
                className="flex items-center justify-between rounded-lg border border-[var(--color-border)] p-3"
              >
                <div>
                  <p className="text-sm font-medium text-[var(--color-ink)]">{mod.display_name || mod.name}</p>
                  <p className="text-xs text-[var(--color-muted)]">{mod.code}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        {plan.companies_using && plan.companies_using.length > 0 && (
          <SectionCard title="Companies Using This Plan">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                    <th className="pb-2 pr-4 font-medium">Company</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 pr-4 font-medium">Start Date</th>
                    <th className="pb-2 font-medium">Expiry Date</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.companies_using.map((cp) => (
                    <tr key={cp.company_id} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-3 pr-4">
                        <button
                          onClick={() => navigate(`/admin/companies/${cp.company_id}`)}
                          className="font-medium text-[var(--color-primary)] hover:underline"
                        >
                          {cp.company_name}
                        </button>
                      </td>
                      <td className="py-3 pr-4"><StatusBadge status={cp.status} /></td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                        {cp.start_date ? new Date(cp.start_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3 text-[var(--color-ink-soft)]">
                        {cp.end_date ? new Date(cp.end_date).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )}

        {/* Edit Plan Modal */}
        {editOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40" onClick={() => setEditOpen(false)} />
            <div className="relative w-full max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                Edit Plan
              </h3>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input
                  label="Plan Name"
                  value={editForm.name || ''}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                />
                <Input
                  label="Description"
                  value={editForm.description || ''}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                />
                <Input
                  label="Monthly Price (₹)"
                  type="number"
                  value={editForm.monthly_price || ''}
                  onChange={(e) => setEditForm({ ...editForm, monthly_price: e.target.value })}
                />
                <Input
                  label="Yearly Price (₹)"
                  type="number"
                  value={editForm.yearly_price || ''}
                  onChange={(e) => setEditForm({ ...editForm, yearly_price: e.target.value })}
                />
                <Input
                  label="Max Employees"
                  type="number"
                  value={editForm.max_employees || ''}
                  onChange={(e) => setEditForm({ ...editForm, max_employees: e.target.value })}
                />
                <Input
                  label="Max OCR Documents"
                  type="number"
                  value={editForm.max_ocr_documents || ''}
                  onChange={(e) => setEditForm({ ...editForm, max_ocr_documents: e.target.value })}
                />
                <Input
                  label="Max Storage (GB)"
                  type="number"
                  value={editForm.max_storage_gb || ''}
                  onChange={(e) => setEditForm({ ...editForm, max_storage_gb: e.target.value })}
                />
                <Input
                  label="Trial Days"
                  type="number"
                  value={editForm.trial_days || ''}
                  onChange={(e) => setEditForm({ ...editForm, trial_days: e.target.value })}
                />
                <Input
                  label="AI Credits"
                  type="number"
                  value={editForm.ai_credits || ''}
                  onChange={(e) => setEditForm({ ...editForm, ai_credits: e.target.value })}
                />
                 <Input
                   label="OCR Credits"
                   type="number"
                   value={editForm.ocr_credits || ''}
                   onChange={(e) => setEditForm({ ...editForm, ocr_credits: e.target.value })}
                 />
                 <div className="sm:col-span-2">
                   <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">
                     Included Modules
                   </label>
                   {loadingModules ? (
                     <p className="text-sm text-[var(--color-muted)]">Loading modules...</p>
                   ) : (
                     <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                       {allModules.map((mod) => (
                         <label key={mod.id} className="flex items-center gap-2 text-sm">
                           <input
                             type="checkbox"
                             checked={(editForm.enabled_models || []).includes(mod.id)}
                             onChange={(e) => {
                               const current = editForm.enabled_models || []
                               if (e.target.checked) {
                                 setEditForm({ ...editForm, enabled_models: [...current, mod.id] })
                               } else {
                                 setEditForm({ ...editForm, enabled_models: current.filter((m) => m !== mod.id) })
                               }
                             }}
                             className="rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                           />
                           <span>{mod.display_name || mod.name}</span>
                         </label>
                       ))}
                     </div>
                   )}
                 </div>
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
