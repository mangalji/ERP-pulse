import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import { netsuiteApi } from '../../services/netsuite.js'

export default function EmployeeNetSuitePage() {
  const { toasts, addToast, removeToast } = useToast()
  const [connection, setConnection] = useState([])
  const [currentConnectionId, setCurrentConnectionId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [switchingId, setSwitchingId] = useState(null)

  useEffect(() => {
    loadConnection()
  }, [])

  const loadConnection = async () => {
    setLoading(true)
    try {
      const data = await netsuiteApi.getMyConnections()

      const list = Array.isArray(data)
        ? data
        : (data?.connections || data?.results || [])
      setConnection(list)
      
      setCurrentConnectionId(
        data?.current_connection_id ||
        data?.currentConnectionId ||
        list.find((item) => item.is_current)?.id ||
        null,
      )

    } catch(err) {
      setConnection([])
      setCurrentConnectionId(null)

      addToast(
        err.payload?.message ||
          err.message ||
          'Failed to load NetSuite connections',
          'error',
      )
    } finally {
      setLoading(false)
    }
  }

  const handleUse = async (connectionId) => {
    if (!connectionId || connectionId === currentConnectionId) {
      return
    }

    setSwitchingId(connectionId)

    try {
      await netsuiteApi.switchConnection(connectionId)

      setCurrentConnectionId(connectionId)

      addToast(
        'NetSuite connection switched successfully',
        'success',
      )

      await loadConnection()
    } catch (err) {
      addToast(
        err.payload?.message ||
          err.message ||
          'Failed to switch NetSuite connection',
        'error',
      )
    } finally {
      setSwitchingId(null)
    }
  }

  if (loading) {
    return (
      <ClientLayout title="NetSuite" breadcrumb="NetSuite">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

return (
  <ClientLayout title="NetSuite" breadcrumb="NetSuite">
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">
          NetSuite
        </h1>

        <p className="mt-1 text-sm text-[var(--color-muted)]">
          Use only the NetSuite accounts assigned to you.
        </p>
      </div>

      {connection.length === 0 ? (
        <Card className="p-6">
          <p className="text-sm text-[var(--color-muted)]">
            No NetSuite connection assigned. Contact your administrator.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {connection.map((connection) => {
            const isCurrent =
              connection.id === currentConnectionId ||
              connection.is_current === true

            return (
              <Card
                key={connection.id}
                className="p-5"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
                      {connection.client_name || 'Unnamed Connection'}
                    </h2>

                    <p className="mt-1 text-sm text-[var(--color-muted)]">
                      {connection.netsuite_account_id} · {connection.environment}
                    </p>

                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge
                        tone={
                          connection.status === 'connected'
                            ? 'positive'
                            : connection.status === 'error'
                              ? 'negative'
                              : 'primary'
                        }
                      >
                        {connection.status}
                      </Badge>

                      {isCurrent && (
                        <Badge tone="primary">
                          Currently Using
                        </Badge>
                      )}
                    </div>
                  </div>

                  <Button
                    intent={isCurrent ? 'secondary' : 'primary'}
                    size="sm"
                    disabled={
                      isCurrent ||
                      switchingId !== null
                    }
                    isLoading={
                      switchingId === connection.id
                    }
                    onClick={() =>
                      handleUse(connection.id)
                    }
                  >
                    {isCurrent ? 'Using' : 'Use'}
                  </Button>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                  <div>
                    <span className="text-[var(--color-muted)]">
                      Connected At:
                    </span>{' '}
                    {connection.connected_at
                      ? new Date(
                          connection.connected_at,
                        ).toLocaleDateString()
                      : '—'}
                  </div>

                  <div>
                    <span className="text-[var(--color-muted)]">
                      Last Synced:
                    </span>{' '}
                    {connection.last_synced_at
                      ? new Date(
                          connection.last_synced_at,
                        ).toLocaleDateString()
                      : '—'}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <Toast
        toasts={toasts}
        removeToast={removeToast}
      />
    </div>
  </ClientLayout>
)
}