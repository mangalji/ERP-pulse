import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'

export default function InvitationExpired({ onResend }) {
  return (
    <Card className="mx-auto max-w-md p-6 text-center">
      <h1 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
        Invitation expired
      </h1>
      <p className="mt-2 text-sm text-[var(--color-muted)]">
        This invitation link has expired. Please request a new one.
      </p>
      {onResend && (
        <Button intent="secondary" onClick={onResend} className="mt-4">
          Resend invitation
        </Button>
      )}
    </Card>
  )
}
