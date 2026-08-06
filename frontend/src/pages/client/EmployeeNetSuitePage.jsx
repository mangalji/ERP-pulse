import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { netsuiteApi } from '../../services/netsuite.js'

export default function EmployeeNetSuitePage() {
  const { toasts, addToast, removeToast } = useToast()
  const [connection, setConnection] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadConnection()
  }, [])

  const loadConnection = async () => {
    setLoading(true)
    try {
      const data = await netsuiteApi.getMyConnection()
      setConnection(data)
    } catch {
      setConnection(null)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <ClientLayout title="NetSuite" breadcrumb="NetSuite">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

  if (!connection) {
    return (
      <ClientLayout title="NetSuite" breadcrumb="NetSuite">
        <Card className="p-6">
          <p className="text-sm text-[var(--color-muted)]">No NetSuite connection assigned. Contact your administrator.</p>
        </Card>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout title="NetSuite" breadcrumb="NetSuite">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">NetSuite Connection</h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">Your assigned NetSuite connection</p>
          </div>
          <Badge tone={connection.status === 'connected' ? 'positive' : 'primary'}>{connection.status}</Badge>
        </div>

        <Card className="p-6">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-[var(--color-muted)]">Connection Name:</span> {connection.client_name || '—'}</div>
            <div><span className="text-[var(--color-muted)]">Account ID:</span> {connection.netsuite_account_id}</div>
            <div><span className="text-[var(--color-muted)]">Environment:</span> {connection.environment}</div>
            <div><span className="text-[var(--color-muted)]">Status:</span> {connection.status}</div>
            <div><span className="text-[var(--color-muted)]">Connected At:</span> {connection.connected_at ? new Date(connection.connected_at).toLocaleDateString() : '—'}</div>
            <div><span className="text-[var(--color-muted)]">Last Synced:</span> {connection.last_synced_at ? new Date(connection.last_synced_at).toLocaleDateString() : '—'}</div>
          </div>
        </Card>

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </ClientLayout>
  )
}
