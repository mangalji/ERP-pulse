import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { demoApi } from '../../services/demo.js'
import { superadminApi } from '../../services/superadmin.js'

const STEPS = ['Company', 'Plan', 'Modules', 'Limits', 'Company Admin']

export default function DemoRequestDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [request, setRequest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [step, setStep] = useState(0)
  const [wizardOpen, setWizardOpen] = useState(false)

  const [companyName, setCompanyName] = useState('')
  const [planId, setPlanId] = useState('')
  const [moduleIds, setModuleIds] = useState([])
  const [adminEmail, setAdminEmail] = useState('')
  const [adminFirstName, setAdminFirstName] = useState('')
  const [adminLastName, setAdminLastName] = useState('')

  const [plans, setPlans] = useState([])
  const [modules, setModules] = useState([])

  useEffect(() => {
    loadRequest()
    loadPlans()
    loadModules()
  }, [id])

  const loadRequest = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await demoApi.get(id)
      setRequest(data)
      setCompanyName(data.company_name || '')
      setAdminEmail(data.business_email || '')
      setAdminFirstName(data.contact_person?.split(' ')[0] || '')
      setAdminLastName(data.contact_person?.split(' ').slice(1).join(' ') || '')
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load demo request')
    } finally {
      setLoading(false)
    }
  }

  const loadPlans = async () => {
    try {
      const data = await superadminApi.listPlans({ limit: 100 })
      setPlans(data.results || [])
    } catch {
      // ignore
    }
  }

  const loadModules = async () => {
    try {
      const data = await superadminApi.listModules({ limit: 100 })
      setModules(data.results || [])
    } catch {
      // ignore
    }
  }

  const handleConvert = async () => {
    setSaving(true)
    try {
      const result = await demoApi.convert(id, {
        plan_id: planId || undefined,
        module_ids: moduleIds.length > 0 ? module_ids : undefined,
        admin_email: adminEmail,
        admin_first_name: adminFirstName,
        admin_last_name: adminLastName,
      })
      addToast('Company converted successfully!', 'success')
      setWizardOpen(false)
      navigate('/admin/companies')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Conversion failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toggleModule = (moduleId) => {
    setModuleIds((prev) =>
      prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]
    )
  }

  if (loading) {
    return (
      <AdminLayout title="Demo Request" breadcrumb="Demo Request">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </AdminLayout>
    )
  }

  if (error) {
    return (
      <AdminLayout title="Demo Request" breadcrumb="Demo Request">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-negative)]">{error}</p>
          <Button intent="secondary" onClick={loadRequest} className="mt-4">Try again</Button>
        </Card>
      </AdminLayout>
    )
  }

  if (!request) return null

  return (
    <AdminLayout title="Demo Request" breadcrumb="Demo Request">
      <div className="flex max-w-3xl flex-col gap-6">
        <PageHeader
          title={`Demo Request ${request.demo_request_number}`}
          subtitle={request.company_name}
          actions={
            request.status === 'APPROVED' || request.status === 'CONTACTED' ? (
              <Button onClick={() => setWizardOpen(true)}>Convert to Company</Button>
            ) : null
          }
        />

        <Card className="p-6">
          <h3 className="mb-4 font-[var(--font-display)] text-sm font-semibold text-[var(--color-ink)]">
            Details
          </h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-[var(--color-muted)]">Contact:</span> {request.contact_person}</div>
            <div><span className="text-[var(--color-muted)]">Email:</span> {request.business_email}</div>
            <div><span className="text-[var(--color-muted)]">Phone:</span> {request.phone}</div>
            <div><span className="text-[var(--color-muted)]">Industry:</span> {request.industry || '—'}</div>
            <div><span className="text-[var(--color-muted)]">Size:</span> {request.company_size || '—'}</div>
            <div><span className="text-[var(--color-muted)]">City:</span> {request.city || '—'}</div>
            <div><span className="text-[var(--color-muted)]">Country:</span> {request.country || '—'}</div>
            <div><span className="text-[var(--color-muted)]">Status:</span> {request.status}</div>
          </div>
          {request.message && (
            <div className="mt-4">
              <span className="text-sm text-[var(--color-muted)]">Message:</span>
              <p className="mt-1 text-sm text-[var(--color-ink)]">{request.message}</p>
            </div>
          )}
        </Card>

        {/* Convert Wizard Modal */}
        {wizardOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40" onClick={() => setWizardOpen(false)} />
            <div className="relative w-full max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
                  Convert to Company
                </h3>
                <button onClick={() => setWizardOpen(false)} className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Step indicator */}
              <div className="mb-6 flex items-center gap-2">
                {STEPS.map((s, i) => (
                  <div key={s} className="flex items-center gap-2">
                    <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      i <= step ? 'bg-[var(--color-primary)] text-white' : 'bg-[var(--color-canvas)] text-[var(--color-muted)]'
                    }`}>
                      {i + 1}
                    </div>
                    <span className={`text-xs ${i <= step ? 'text-[var(--color-ink)]' : 'text-[var(--color-muted)]'}`}>{s}</span>
                    {i < STEPS.length - 1 && <div className="mx-1 h-px w-4 bg-[var(--color-border)]" />}
                  </div>
                ))}
              </div>

              <div className="max-h-[60vh] overflow-y-auto">
                {step === 0 && (
                  <div className="flex flex-col gap-4">
                    <Input label="Company Name" value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
                  </div>
                )}

                {step === 1 && (
                  <div className="flex flex-col gap-4">
                    <label className="flex flex-col gap-1.5">
                      <span className="text-sm font-medium text-[var(--color-ink-soft)]">Plan</span>
                      <select
                        value={planId}
                        onChange={(e) => setPlanId(e.target.value)}
                        className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
                      >
                        <option value="">Select a plan</option>
                        {plans.map((plan) => (
                          <option key={plan.id} value={plan.id}>{plan.name}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}

                {step === 2 && (
                  <div className="flex flex-col gap-3">
                    <p className="text-sm text-[var(--color-muted)]">Select modules to enable:</p>
                    {modules.map((mod) => (
                      <label key={mod.id} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] p-3">
                        <input
                          type="checkbox"
                          checked={moduleIds.includes(mod.id)}
                          onChange={() => toggleModule(mod.id)}
                          className="rounded border-[var(--color-border)]"
                        />
                        <div>
                          <p className="text-sm font-medium text-[var(--color-ink)]">{mod.display_name || mod.name}</p>
                          <p className="text-xs text-[var(--color-muted)]">{mod.code}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                )}

                {step === 3 && (
                  <div className="flex flex-col gap-4">
                    <p className="text-sm text-[var(--color-muted)]">Usage limits are inherited from the selected plan.</p>
                    {planId && (
                      <div className="rounded-lg border border-[var(--color-border)] p-4">
                        {(() => {
                          const plan = plans.find((p) => p.id === planId)
                          if (!plan) return <p className="text-sm text-[var(--color-muted)]">Select a plan first.</p>
                          return (
                            <div className="grid grid-cols-3 gap-4 text-sm">
                              <div><span className="text-[var(--color-muted)]">Employees:</span> {plan.max_employees}</div>
                              <div><span className="text-[var(--color-muted)]">OCR Docs:</span> {plan.max_ocr_documents}</div>
                              <div><span className="text-[var(--color-muted)]">Storage:</span> {plan.max_storage_gb} GB</div>
                            </div>
                          )
                        })()}
                      </div>
                    )}
                  </div>
                )}

                {step === 4 && (
                  <div className="flex flex-col gap-4">
                    <Input label="Admin Email" type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required />
                    <div className="grid grid-cols-2 gap-3">
                      <Input label="First Name" value={adminFirstName} onChange={(e) => setAdminFirstName(e.target.value)} required />
                      <Input label="Last Name" value={adminLastName} onChange={(e) => setAdminLastName(e.target.value)} required />
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 flex items-center justify-between">
                <Button
                  intent="secondary"
                  onClick={() => setStep((s) => Math.max(0, s - 1))}
                  disabled={step === 0}
                >
                  Previous
                </Button>
                {step < STEPS.length - 1 ? (
                  <Button onClick={() => setStep((s) => s + 1)}>Next</Button>
                ) : (
                  <Button onClick={handleConvert} isLoading={saving}>
                    Finish
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </AdminLayout>
  )
}
