import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import SubscriptionCard from '../../components/subscriptions/SubscriptionCard.jsx'
import UsageCard from '../../components/subscriptions/UsageCard.jsx'
import LimitProgress from '../../components/subscriptions/LimitProgress.jsx'
import { subscriptionApi } from '../../services/subscriptions.js'

export default function ClientSubscriptionPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [subscription, setSubscription] = useState(null)
  const [usage, setUsage] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [subData, usageData] = await Promise.all([
        subscriptionApi.getMySubscription(),
        subscriptionApi.getMyUsage(),
      ])
      setSubscription(subData)
      setUsage(usageData || [])
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load subscription', 'error')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <ClientLayout title="Subscription" breadcrumb="Subscription">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout title="Subscription" breadcrumb="Subscription">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
              Subscription
            </h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Manage your plan and usage
            </p>
          </div>
          <Badge tone={subscription?.status === 'ACTIVE' ? 'positive' : 'primary'}>
            {subscription?.status || 'No Plan'}
          </Badge>
        </div>

        <SubscriptionCard
          planName={subscription?.plan_name}
          status={subscription?.status}
          startDate={subscription?.start_date}
          endDate={subscription?.end_date}
          isAutoRenew={subscription?.is_auto_renew}
          onRenew={subscription?.status === 'EXPIRED' || subscription?.status === 'CANCELLED' ? loadData : undefined}
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {usage.map((item) => (
            <LimitProgress
              key={item.module_code}
              label={item.module_name}
              used={item.usage_count}
              limit={item.usage_limit}
            />
          ))}
        </div>

        <UsageCard modules={usage} />

        <div className="flex justify-end">
          <Button intent="secondary" onClick={() => addToast('Upgrade requests are handled by AGSuite support.', 'success')}>
            Request Upgrade
          </Button>
        </div>

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </ClientLayout>
  )
}
