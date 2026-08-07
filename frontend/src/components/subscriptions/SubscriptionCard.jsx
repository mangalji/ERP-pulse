import Card from '../ui/Card.jsx'

export default function SubscriptionCard({ planName, status, startDate, endDate, isAutoRenew,
                                          originalPrice, discountDisplay, finalPrice, billingCycle,
                                          onUpgrade, onRenew }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">{planName || 'No Active Plan'}</h3>
          <p className="mt-1 text-sm text-[var(--color-muted)]">Status: {status}</p>
          {startDate && <p className="mt-0.5 text-xs text-[var(--color-muted)]">Started: {new Date(startDate).toLocaleDateString()}</p>}
          {endDate && <p className="mt-0.5 text-xs text-[var(--color-muted)]">Expires: {new Date(endDate).toLocaleDateString()}</p>}
          {isAutoRenew && <p className="mt-0.5 text-xs text-[var(--color-positive)]">Auto-renew enabled</p>}
          {originalPrice !== undefined && (
            <div className="mt-2 flex gap-4 text-xs">
              <span className="text-[var(--color-muted)]">Original: ₹{Number(originalPrice || 0).toFixed(2)}/{billingCycle === 'YEARLY' ? 'yr' : 'mo'}</span>
              {discountDisplay && <span className="text-[var(--color-warning)]">Discount: {discountDisplay}</span>}
              <span className="font-medium text-[var(--color-primary)]">Final: ₹{Number(finalPrice || 0).toFixed(2)}/{billingCycle === 'YEARLY' ? 'yr' : 'mo'}</span>
            </div>
          )}
        </div>
        <div className="flex gap-2">
          {onUpgrade && <button onClick={onUpgrade} className="rounded-md px-3 py-1.5 text-xs font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">Upgrade</button>}
          {onRenew && <button onClick={onRenew} className="rounded-md px-3 py-1.5 text-xs font-medium text-[var(--color-positive)] hover:bg-[var(--color-positive-soft)]">Renew</button>}
        </div>
      </div>
    </Card>
  )
}
