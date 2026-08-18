import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import AdminLayout from '../../components/layout/AdminLayout.jsx'
import PageHeader from '../../components/superadmin/PageHeader.jsx'
import StatCard from '../../components/superadmin/StatCard.jsx'
import SectionCard from '../../components/superadmin/SectionCard.jsx'
import StatusBadge from '../../components/superadmin/StatusBadge.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import Button from '../../components/ui/Button.jsx'
import { superadminApi } from '../../services/superadmin.js'

const statIcons = {
  companies: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6" />
    </svg>
  ),
  active: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" />
      <path d="M22 4 12 14l-3-3" />
    </svg>
  ),
  trial: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M12 8v4l3 3M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  suspended: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="12" cy="12" r="9" />
      <path d="M10 9l4 6M14 9l-4 6" />
    </svg>
  ),
  agsuite: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="9" cy="7" r="3" />
      <path d="M3 21v-2a6 6 0 0 1 12 0v2" />
      <path d="M16 4a3 3 0 0 1 0 6" />
    </svg>
  ),
  client: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <circle cx="9" cy="7" r="3" />
      <path d="M3 21v-2a6 6 0 0 1 12 0v2" />
    </svg>
  ),
  plans: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M12 18v-6M9 15l3 3 3-3" />
    </svg>
  ),
  support: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  modules: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDashboard = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await superadminApi.getDashboardSummary()
      setSummary(data)
    } catch (err) {
      setError(err.payload?.message || err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const stats = useMemo(() => {
    if (!summary) return []
    return [
      { id: 'companies', label: 'Total Companies', value: summary.total_companies, icon: statIcons.companies },
      { id: 'active', label: 'Active Companies', value: summary.active_companies, icon: statIcons.active },
      { id: 'trial', label: 'Trial Companies', value: summary.trial_companies, icon: statIcons.trial },
      { id: 'suspended', label: 'Suspended Companies', value: summary.suspended_companies, icon: statIcons.suspended },
      { id: 'agsuite', label: 'AGSuite Employees', value: summary.total_agsuite_employees, icon: statIcons.agsuite },
      { id: 'client', label: 'Client Employees', value: summary.total_client_employees, icon: statIcons.client },
      { id: 'plans', label: 'Plans', value: summary.total_plans, icon: statIcons.plans },
      { id: 'support', label: 'Support Sessions', value: summary.total_support_sessions, icon: statIcons.support },
      { id: 'modules', label: 'Modules', value: summary.total_modules, icon: statIcons.modules },
    ]
  }, [summary])

  return (
    <AdminLayout title="Dashboard" breadcrumb="Dashboard">
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Platform Overview"
          subtitle="A high-level view of companies, users, plans, and modules across AGSuite."
          actions={
            <Button intent="secondary" onClick={() => navigate('/admin/companies')}>
              View Companies
            </Button>
          }
        />

        {error ? (
          <SectionCard title="Dashboard">
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <p className="text-sm text-[var(--color-negative)]">{error}</p>
              <Button intent="secondary" onClick={loadDashboard}>Try again</Button>
            </div>
          </SectionCard>
        ) : (
          <>
            {loading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 9 }).map((_, i) => (
                  <Skeleton key={i} className="h-28 w-full" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {stats.map((stat) => (
                  <StatCard key={stat.id} {...stat} />
                ))}
              </div>
            )}

            {/* <SectionCard title="Recent Companies">
              {loading ? (
                <Skeleton className="h-40 w-full" />
              ) : recentCompanies.length === 0 ? (
                <EmptyState title="No companies yet" description="New company registrations will appear here." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-[var(--color-border)]">
                        <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Name</th>
                        <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Code</th>
                        <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Status</th>
                        <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentCompanies.map((company) => (
                        <tr key={company.id} className="border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-canvas)]">
                          <td className="px-4 py-3">
                            <button
                              onClick={() => navigate(`/admin/companies/${company.id}`)}
                              className="font-medium text-[var(--color-primary)] hover:underline"
                            >
                              {company.name}
                            </button>
                          </td>
                          <td className="px-4 py-3 text-[var(--color-ink-soft)]">{company.code}</td>
                          <td className="px-4 py-3"><StatusBadge status={company.status} /></td>
                          <td className="px-4 py-3 text-[var(--color-muted)]">
                            {company.created_at ? new Date(company.created_at).toLocaleDateString() : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard> */}
          </>
        )}
      </div>
    </AdminLayout>
  )
}
