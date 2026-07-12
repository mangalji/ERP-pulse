import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function SettingsPage() {
  const { netSuiteConnected } = useAuth()

  return (
    <DashboardLayout title="Settings">
      <div className="flex max-w-xl flex-col gap-6">
        <Card className="p-6">
          <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
            Profile
          </h2>
          <form className="mt-4 flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Input id="settingsFirstName" label="First name" defaultValue="Jane" />
              <Input id="settingsLastName" label="Last name" defaultValue="Doe" />
            </div>
            <Input id="settingsEmail" type="email" label="Email" defaultValue="jane@company.com" disabled />
            <Input id="settingsMobile" type="tel" label="Mobile number" defaultValue="+1 555 123 4567" />
            <Button type="submit" className="w-fit">
              Save changes
            </Button>
          </form>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              NetSuite Connection
            </h2>
            <Badge tone={netSuiteConnected ? 'positive' : 'netsuite'}>
              {netSuiteConnected ? 'Connected' : 'Not connected'}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-[var(--color-muted)]">
            Manage or disconnect your NetSuite account from here.
          </p>
        </Card>
      </div>
    </DashboardLayout>
  )
}
