import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Select from '../../components/ui/Select.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import SubscriptionCard from '../../components/subscriptions/SubscriptionCard.jsx'
import ModuleGrid from '../../components/subscriptions/ModuleGrid.jsx'
import UsageCard from '../../components/subscriptions/UsageCard.jsx'
import PlanHistoryTable from '../../components/subscriptions/PlanHistoryTable.jsx'
import { subscriptionApi } from '../../services/subscriptions.js'
import { superadminApi } from '../../services/superadmin.js'

const TABS = [
  { key: 'subscription', label: 'Subscription' },
  { key: 'modules', label: 'Modules' },
  { key: 'usage', label: 'Usage' },
  { key: 'history', label: 'History' },
]

export default function CompanySubscriptionPage() {
  const { id } = useParams()
  const { toasts, addToast, removeToast } = useToast()
  const [tab, setTab] = useState('subscription')
  const [subscription, setSubscription] = useState(null)
  const [modules, setModules] = useState([])
  const [usage, setUsage] = useState([])
  const [history, setHistory] = useState([])
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState('')

  useEffect(() => {
    loadData()
  }, [id])

  const loadData = async () => {
    setLoading(true)
    try {
      const [subData, modData, usageData, histData, plansData] = await Promise.all([
        superadminApi.getCompany(id),
        superadminApi.fetchCompanyModules(id),
        subscriptionApi.getMyUsage(),
        subscriptionApi.getCompanyPlanHistory(id),
        subscriptionApi.listPlans(),
      ])
      setSubscription(subData)
      setModules(modData.results || modData || [])
      setUsage(usageData || [])
      setHistory(histData || [])
      setPlans(plansData.results || plansData || [])
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleAssignPlan = async () => {
    if (!selectedPlan) return
    setSaving(true)
    try {
      await subscriptionApi.assignPlan({ company_id: id, plan_id: selectedPlan, status: 'TRIAL' })
      addToast('Plan assigned successfully', 'success')
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to assign plan', 'error')
    } finally {
      setSaving(false)
    }
  }

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

  return (
    <AdminLayout title="Company Subscription" breadcrumb="Subscription">
      <div className="flex flex-col gap-6">
        <PageHeader
          title={subscription?.name || 'Company'}
          subtitle={`Subscription management for ${subscription?.name || ''}`}
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
            <Card className="p-5">
              <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Current Plan</h3>
              <SubscriptionCard
                planName={subscription?.plan_name}
                status={subscription?.status}
                startDate={subscription?.start_date}
                endDate={subscription?.end_date}
                isAutoRenew={subscription?.is_auto_renew}
              />
            </Card>
            <Card className="p-5">
              <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">Assign Plan</h3>
              <div className="flex gap-2">
                <Select value={selectedPlan} onChange={(e) => setSelectedPlan(e.target.value)} className="flex-1">
                  <option value="">Select a plan</option>
                  {plans.map((plan) => (
                    <option key={plan.id} value={plan.id}>{plan.name} - ${plan.monthly_price}/mo</option>
                  ))}
                </Select>
                <Button onClick={handleAssignPlan} isLoading={saving}>Assign</Button>
              </div>
            </Card>
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

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </AdminLayout>
  )
}
