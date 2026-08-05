import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
import InfoCard from '../../components/superadmin/InfoCard.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <AdminLayout title="Settings" breadcrumb="Settings">
      <div className="flex flex-col gap-6">
        <PageHeader title="Settings" subtitle="Manage your AGSuite super admin preferences." />

        <SectionCard title="Profile">
          <InfoCard
            items={[
              { label: 'Name', value: user ? `${user.first_name} ${user.last_name}`.trim() : '—' },
              { label: 'Email', value: user?.email || '—' },
              { label: 'Role', value: 'Super Admin' },
            ]}
          />
        </SectionCard>

        <SectionCard title="Theme">
          <p className="text-sm text-[var(--color-muted)]">
            Theme preferences are prepared but not yet enabled. The light theme is currently active.
          </p>
        </SectionCard>

        <SectionCard title="Security">
          <p className="text-sm text-[var(--color-muted)]">
            Manage your account security settings, password, and session details.
          </p>
        </SectionCard>
      </div>
    </AdminLayout>
  )
}
