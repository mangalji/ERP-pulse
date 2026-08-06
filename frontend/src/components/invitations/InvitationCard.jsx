import Card from '../ui/Card.jsx'

export default function InvitationCard({ companyName, email, expiresAt, onResend }) {
  return (
    <Card className="mx-auto max-w-md p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-bold text-white">
          A
        </span>
        <div>
          <h1 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
            You're invited!
          </h1>
          <p className="text-sm text-[var(--color-muted)]">{companyName}</p>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-2 text-sm text-[var(--color-ink-soft)]">
        <p><span className="font-medium">Email:</span> {email}</p>
        <p><span className="font-medium">Expires:</span> {new Date(expiresAt).toLocaleString()}</p>
      </div>

      {onResend && (
        <button
          onClick={onResend}
          className="text-sm font-medium text-[var(--color-primary)] hover:underline"
        >
          Resend invitation
        </button>
      )}
    </Card>
  )
}
