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
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [txLoading, setTxLoading] = useState(false)

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
      try {
        setTxLoading(true)
        const txData = await subscriptionApi.getMyTransactions()
        setTransactions(txData?.results || txData || [])
      } catch {
        setTransactions([])
      } finally {
        setTxLoading(false)
      }
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
          originalPrice={subscription?.original_price}
          discountDisplay={subscription?.discount_display}
          finalPrice={subscription?.final_price}
          billingCycle={subscription?.billing_cycle}
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

        {transactions.length > 0 && (
          <Card className="p-5">
            <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              My Transactions
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-xs text-[var(--color-muted)]">
                    <th className="pb-2 pr-4 font-medium">Transaction ID</th>
                    <th className="pb-2 pr-4 font-medium">Plan</th>
                    <th className="pb-2 pr-4 font-medium">Original Amount</th>
                    <th className="pb-2 pr-4 font-medium">Discount</th>
                    <th className="pb-2 pr-4 font-medium">Final Amount</th>
                    <th className="pb-2 pr-4 font-medium">Billing Cycle</th>
                    <th className="pb-2 pr-4 font-medium">Status</th>
                    <th className="pb-2 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs text-[var(--color-ink)]">{tx.transaction_id}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{tx.plan?.name || '—'}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">₹{Number(tx.original_amount).toFixed(2)}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">
                        -₹{(Number(tx.original_amount) - Number(tx.final_amount)).toFixed(2)}
                      </td>
                      <td className="py-3 pr-4 font-medium text-[var(--color-primary)]">₹{Number(tx.final_amount).toFixed(2)}</td>
                      <td className="py-3 pr-4 text-[var(--color-ink-soft)]">{tx.billing_cycle || '—'}</td>
                      <td className="py-3 pr-4 capitalize">{tx.payment_status}</td>
                      <td className="py-3 pr-4 text-[var(--color-muted)]">
                        {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

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
