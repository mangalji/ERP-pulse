export default function TopCustomersBar({ customers }) {
  return (
    <ul className="flex flex-col gap-4">
      {customers.map((customer) => (
        <li key={customer.id}>
          <div className="mb-1.5 flex items-center justify-between text-sm">
            <span className="font-medium text-[var(--color-ink)]">{customer.name}</span>
            {/* <span className="font-mono-tabular text-[var(--color-muted)]">
              ${customer.value.toLocaleString('en-US')}
            </span> */}
            <span className="font-mono-tabular text-[var(--color-muted)]">
              ${(Number(customer.value) || 0).toLocaleString('en-US')}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-canvas)]">
            <div
              className="h-full rounded-full bg-[var(--color-primary)]"
              style={{
  width: `${Math.max(0, Number(customer.share) || 0)}%`
}}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
