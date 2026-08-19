import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Input from '../../components/ui/Input.jsx'
import Select from '../../components/ui/Select.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import SubscriptionCard from '../../components/subscriptions/SubscriptionCard.jsx'
import ModuleGrid from '../../components/subscriptions/ModuleGrid.jsx'
import UsageCard from '../../components/subscriptions/UsageCard.jsx'
import PlanHistoryTable from '../../components/subscriptions/PlanHistoryTable.jsx'
import { superadminApi } from '../../services/superadmin.js'
import { subscriptionApi } from '../../services/subscriptions.js'

const TABS = [
  { key: 'subscription', label: 'Subscription' },
  { key: 'modules', label: 'Modules' },
  { key: 'usage', label: 'Usage' },
  { key: 'history', label: 'History' },
  { key: 'transactions', label: 'Transactions' },
]

export default function CompanySubscriptionPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()
  const [tab, setTab] = useState('subscription')
  const [company, setCompany] = useState(null)
  const [modules, setModules] = useState([])
  const [usage, setUsage] = useState([])
  const [history, setHistory] = useState([])
  const [plans, setPlans] = useState([])
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState('')
  const [discountType, setDiscountType] = useState('NONE')
  const [discountValue, setDiscountValue] = useState('')
  const [effectivePrice, setEffectivePrice] = useState(0)

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    setLoading(true)
    try {
      const [companyData, modData, histData, plansData] = await Promise.all([
        superadminApi.getCompany(id),
        superadminApi.fetchCompanyModules(id),
        subscriptionApi.getCompanyPlanHistory(id),
        superadminApi.listPlans(),
      ])
      setCompany(companyData)
      setModules(modData.results || modData || [])
      setHistory(histData || [])
      setPlans(plansData.results || plansData || [])
      try {
        const txData = await superadminApi.fetchCompanyTransactions(id)
        setTransactions(txData.results || txData || [])
      } catch {
        setTransactions([])
      }
      try {
        const usageData = await subscriptionApi.getMyUsage()
        setUsage(usageData || [])
      } catch {
        setUsage([])
      }
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const currentPlan = company?.current_plan || null
  const pendingTransaction = transactions.find(tx => tx.payment_status === 'PENDING')
  const completedTransaction = transactions.find(tx => tx.payment_status === 'SUCCESS')

  const flowState = currentPlan
    ? 'active'
    : pendingTransaction
      ? 'pending'
      : 'assign'

  const handleAssignPlan = async () => {
    if (!selectedPlan) return
    setSaving(true)
    try {
      await superadminApi.assignPlanPending({
        company_id: id,
        plan_id: selectedPlan,
        discount_type: discountType,
        discount_value: 
          discountValue === 'NONE'
           ? 0
           : Number(discountValue) || 0,
      })
      addToast('Plan assigned. Payment pending.', 'success')
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to assign plan', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleCompleteTransaction = async () => {
    if (!pendingTransaction) return
    setSaving(true)
    try {
      await superadminApi.completeTransaction({
        transaction_id: pendingTransaction.transaction_id,
      })
      addToast('Transaction completed. Subscription activated.', 'success')
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to complete transaction', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handlePlanChange = (planId) => {
    setSelectedPlan(planId)
  }

  const handleDiscountChange = (type) => {
    setDiscountType(type)
    if (type === 'NONE') setDiscountValue('')
  }

  useEffect(() => {
    if (!selectedPlan) {
      setEffectivePrice(0)
      return
    }
    const plan = plans.find((p) => p.id === selectedPlan)
    if (!plan) return
    const original = Number(plan.price || 0)
    const discountNum = Number(discountValue) || 0
    let final = original
    if (discountType === 'PERCENTAGE') {
      final = original - (original * discountNum / 100)
    } else if (discountType === 'FIXED') {
      final = original - discountNum
    }
    setEffectivePrice(Math.max(final, 0))
  }, [selectedPlan, discountType, discountValue, plans])

  const handleToggleModule = async (moduleId) => {
    const mod = modules.find((m) => m.module === moduleId)
    if (!mod) return
    try {
      if (mod.enabled) {
        await subscriptionApi.disableModule({ company_id: id, module_id: moduleId })
      } else {
        await subscriptionApi.enableModule({ company_id: id, module_id: moduleId })
      }
      addToast('Module updated successfully', 'success')
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to update module', 'error')
    }
  }

  if (loading) {
    return (
      <AdminLayout title="Company Subscription" breadcrumb="Subscription">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </AdminLayout>
    )
  }

  const selectedPlanData = plans.find((p) => p.id === selectedPlan)

  return (
    <AdminLayout title="Company Subscription" breadcrumb="Subscription">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/admin/companies/${id}`)}
            className="rounded-lg p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-4 w-4">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--color-muted)]">Company Detail</span>
        </div>
        <PageHeader
          title={company?.name || 'Company'}
          subtitle={`Subscription management for ${company?.name || ''}`}
        />

        <div className="flex gap-2 border-b border-[var(--color-border)]">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                tab === t.key
                  ? 'border-b-2 border-[var(--color-primary)] text-[var(--color-primary)]'
                  : 'text-[var(--color-muted)] hover:text-[var(--color-ink)]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'subscription' && (
          <div className="flex flex-col gap-4">
            {flowState === 'assign' && (
              <Card className="p-5">
                <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Assign Plan</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Select Plan</label>
                    <Select value={selectedPlan} onChange={(e) => handlePlanChange(e.target.value)} className="flex-1">
                      <option value="">Select a plan</option>
                      {plans.map((plan) => (
                        <option key={plan.id} value={plan.id}>
                          {plan.name} - ₹{plan.price}
                        </option>
                      ))}
                    </Select>
                  </div>
                  {selectedPlanData && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Plan Price</label>
                        <Input type="number" value={selectedPlanData.price || 0} readOnly className="bg-[var(--color-canvas)]" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Validity</label>
                        <Input type="number" value={selectedPlanData.validity_days || 30} readOnly className="bg-[var(--color-canvas)]" />
                      </div>
                    </>
                  )}
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Discount Type</label>
                    <Select value={discountType} onChange={(e) => handleDiscountChange(e.target.value)} className="w-full">
                      <option value="NONE">No Discount</option>
                      <option value="PERCENTAGE">Percentage (%)</option>
                      <option value="FIXED">Fixed Amount (₹)</option>
                    </Select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Discount Value</label>
                    <Input
                      type="number"
                      value={discountValue}
                      onChange={(e) => setDiscountValue(e.target.value)}
                      disabled={discountType === 'NONE'}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
                      <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Final Amount</label>
                      <p className="text-2xl font-bold text-[var(--color-primary)]">
                        ₹{effectivePrice.toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button onClick={handleAssignPlan} isLoading={saving} disabled={!selectedPlan}>Assign Plan</Button>
                </div>
              </Card>
            )}

            {flowState === 'pending' && pendingTransaction && (
              <Card className="p-5">
                <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Payment Pending</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Plan</label>
                    <p className="text-sm font-medium text-[var(--color-ink)]">{pendingTransaction.plan__name || '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Original Price</label>
                    <p className="text-sm font-medium text-[var(--color-ink-soft)]">₹{Number(pendingTransaction.original_amount || 0).toFixed(2)}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Discount</label>
                    <p className="text-sm font-medium text-[var(--color-ink-soft)]">-₹{Number(pendingTransaction.discount_amount || 0).toFixed(2)}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Final Amount</label>
                    <p className="text-sm font-bold text-[var(--color-primary)]">₹{Number(pendingTransaction.final_amount || 0).toFixed(2)}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Transaction ID</label>
                    <p className="text-sm font-mono text-[var(--color-ink)]">{pendingTransaction.transaction_id || '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Payment Status</label>
                    <p className="text-sm font-medium text-[var(--color-ink-soft)]">Pending</p>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button onClick={handleCompleteTransaction} isLoading={saving}>Transaction Completed</Button>
                </div>
              </Card>
            )}

            {flowState === 'active' && currentPlan && (
              <Card className="p-5">
                <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Subscription Active</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Plan</label>
                    <p className="text-sm font-medium text-[var(--color-ink)]">{currentPlan.plan_name || '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Final Price</label>
                    <p className="text-sm font-bold text-[var(--color-primary)]">₹{Number(currentPlan.final_price || 0).toFixed(2)}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Transaction ID</label>
                    <p className="text-sm font-mono text-[var(--color-ink)]">{completedTransaction?.transaction_id || '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Payment Status</label>
                    <p className="text-sm font-medium text-[var(--color-ink-soft)]">{completedTransaction ? 'Completed' : '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Subscription Status</label>
                    <p className="text-sm font-medium text-[var(--color-ink-soft)]">{currentPlan.status || '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Start Date</label>
                    <p className="text-sm text-[var(--color-ink-soft)]">{currentPlan.start_date ? new Date(currentPlan.start_date).toLocaleDateString() : '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">End Date</label>
                    <p className="text-sm text-[var(--color-ink-soft)]">{currentPlan.end_date ? new Date(currentPlan.end_date).toLocaleDateString() : '—'}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[var(--color-ink-soft)] mb-1">Validity</label>
                    <p className="text-sm text-[var(--color-ink-soft)]">{currentPlan.validity_days ?? 30} days</p>
                  </div>
                </div>
              </Card>
            )}
          </div>
        )}

        {tab === 'modules' && (
          <ModuleGrid
            modules={modules.map((m) => ({ id: m.module, name: m.module_name, code: m.module_code, display_name: m.module_name }))}
            enabledIds={modules.filter((m) => m.enabled).map((m) => m.module)}
            onToggle={(moduleId) => handleToggleModule(moduleId)}
          />
        )}

        {tab === 'usage' && <UsageCard modules={usage} />}

        {tab === 'history' && <PlanHistoryTable history={history} />}

        {tab === 'transactions' && (
          <Card className="p-5">
            <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              Transaction History
            </h3>
            {transactions.length === 0 ? (
              <p className="text-sm text-[var(--color-muted)]">No transactions found.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                      <th className="pb-2 pr-4 font-medium">Transaction ID</th>
                      <th className="pb-2 pr-4 font-medium">Plan</th>
                      <th className="pb-2 pr-4 font-medium">Amount</th>
                      <th className="pb-2 pr-4 font-medium">Discount</th>
                      <th className="pb-2 pr-4 font-medium">Final Amount</th>
                      <th className="pb-2 pr-4 font-medium">Status</th>
                      <th className="pb-2 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => (
                      <tr key={tx.id} className="border-b border-[var(--color-border)] last:border-0">
                        <td className="py-3 pr-4 font-mono text-xs text-[var(--color-ink)]">{tx.transaction_id}</td>
                        <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{tx.plan__name || '—'}</td>
                        <td className="py-3 pr-4 text-[var(--color-ink-soft)]">₹{Number(tx.original_amount || 0).toFixed(2)}</td>
                        <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                          -₹{Number(tx.discount_amount || 0).toFixed(2)}
                        </td>
                        <td className="py-3 pr-4 font-medium text-[var(--color-primary)]">₹{Number(tx.final_amount || 0).toFixed(2)}</td>
                        <td className="py-3 pr-4"><span className="capitalize">{tx.payment_status}</span></td>
                        <td className="py-3 pr-4 text-[var(--color-muted)]">
                          {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </AdminLayout>
  )
}
