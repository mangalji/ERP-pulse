import Card from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import { Link } from 'react-router-dom'

export default function InvitationSuccess() {
  return (
    <Card className="mx-auto max-w-md p-6 text-center">
      <h1 className="font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)]">
        Account created!
      </h1>
      <p className="mt-2 text-sm text-[var(--color-muted)]">
        Your account has been set up successfully. You can now log in.
      </p>
      <Link to="/login">
        <Button intent="primary" className="mt-4">
          Go to login
        </Button>
      </Link>
    </Card>
  )
}
