import { useState, useEffect } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import Card from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Toast, { useToast } from '../../components/ui/Toast.jsx'
import ConnectionForm from '../../components/netsuite/ConnectionForm.jsx'
import ConnectionCard from '../../components/netsuite/ConnectionCard.jsx'
import ConnectionTable from '../../components/netsuite/ConnectionTable.jsx'
import AssignEmployeesDialog from '../../components/netsuite/AssignEmployeesDialog.jsx'
import { netsuiteApi } from '../../services/netsuite.js'
import { clientApi } from '../../services/client.js'

export default function NetSuiteIntegrationsPage() {
  const { toasts, addToast, removeToast } = useToast()
  const [connections, setConnections] = useState([])
  const [currentConnectionId, setCurrentConnectionId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [assigningId, setAssigningId] = useState(null)
  const [companyEmployees, setCompanyEmployees] = useState([])

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [connData, empData, currentData] = await Promise.all([
        netsuiteApi.getCompanyConnections(),
        clientApi.listEmployees({ limit: 100 }),
        netsuiteApi.getMyConnection().catch(() => null),
      ])
      const list = Array.isArray(connData)
        ? connData
        : (connData?.connections || connData?.results || [])

      setConnections(list)
      setCompanyEmployees(empData?.results ?? empData ?? [])
      setCurrentConnectionId(
        currentData?.id ||
        currentData?.connection_id ||
        currentData?.connection?.id ||
        null,
      )
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to load connections', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (formData) => {
    setSaving(true)
    try {
      const result = await netsuiteApi.createConnection(formData)
      if (!result?.authorization_url){
        throw new Error(
          'NetSuite authorization URL was not returned.',
        )
      }
      window.location.href = result.authorization_url
      // addToast('Connection created. Complete OAuth to activate.', 'success')
      // setShowForm(false)
      // loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to create connection', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleUse = async (id) => {
  if (!id || id === currentConnectionId) {
    return
  }

  try {
    await netsuiteApi.switchConnection(id)

    setCurrentConnectionId(id)

    addToast(
      'NetSuite connection switched successfully',
      'success',
    )

    await loadData()
  } catch (err) {
    addToast(
      err.payload?.message ||
        err.message ||
        'Failed to switch NetSuite connection',
      'error',
    )
  }
}

  const handleTest = async (id) => {
    try {
      const result = await netsuiteApi.testConnection(id)
      addToast(result.message, result.success ? 'success' : 'error')
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Test failed', 'error')
    }
  }

  const handleAssign = async (connectionId) => {
    setAssigningId(connectionId)
  }

  const handleAssignSubmit = async (employeeId) => {
    if (!assigningId) return
    try {
      await netsuiteApi.assignEmployee(assigningId, employeeId)
      addToast('Employee assigned', 'success')
      setAssigningId(null)
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to assign employee', 'error')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this connection?')) return
    try {
      await netsuiteApi.deleteConnection(id)
      addToast('Connection deleted', 'success')
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to delete connection', 'error')
    }
  }

  const handleRemoveEmployee = async (
  connectionId,
  employeeId,
) => {
  try {
    await netsuiteApi.removeEmployee(
      connectionId,
      employeeId,
    )

    addToast(
      'Employee removed from this NetSuite account',
      'success',
    )

    await loadData()
  } catch (err) {
    addToast(
      err.payload?.message ||
        err.message ||
        'Failed to remove employee',
      'error',
    )

    throw err
  }
}

  if (loading) {
    return (
      <ClientLayout title="Integrations" breadcrumb="Integrations">
        <Card className="p-6"><p className="text-sm text-[var(--color-muted)]">Loading...</p></Card>
      </ClientLayout>
    )
  }

  return (
    <ClientLayout title="Integrations" breadcrumb="Integrations">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold text-[var(--color-ink)]">NetSuite Integration</h1>
            <p className="mt-1 text-sm text-[var(--color-muted)]">Manage your company's NetSuite connections.</p>
          </div>
          <Button onClick={() => { setEditingId(null); setShowForm(true); }}>New Connection</Button>
        </div>

        {showForm && (
          <Card className="p-6">
            <h3 className="mb-4 font-[var(--font-display)] text-base font-semibold text-[var(--color-ink)]">
              {editingId ? 'Edit Connection' : 'Create Connection'}
            </h3>
            <ConnectionForm onSubmit={handleCreate} isLoading={saving} />
            <Button intent="secondary" onClick={() => { setShowForm(false); setEditingId(null); }} className="mt-4">Cancel</Button>
          </Card>
        )}

        {connections.length === 0 ? (
          <Card className="p-6">
            <p className="text-sm text-[var(--color-muted)]">No NetSuite connections yet. Create one to get started.</p>
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            {connections.map((conn) => (
              <ConnectionCard
                key={conn.id}
                connection={conn}
                isCurrent={conn.id === currentConnectionId}
                onUse={handleUse}
                onTest={handleTest}
                onAssign={handleAssign}
                onRemoveEmployee={handleRemoveEmployee}
                onDelete={handleDelete}
                onEdit={(c) => { setEditingId(c.id); setShowForm(true); }}
                employees={conn.employee_assignments || []}
              />
            ))}
          </div>
        )}

        {assigningId && (
          <AssignEmployeesDialog
            connectionId={assigningId}
            employees={companyEmployees}
            assignedEmployees={
              connections.find(
                (connection) =>
                  connection.id === assigningId
              )?.employee_assignments || []
            }
            onClose={() => setAssigningId(null)}
            onAssigned={loadData}
          />
        )}

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </ClientLayout>
  )
}
