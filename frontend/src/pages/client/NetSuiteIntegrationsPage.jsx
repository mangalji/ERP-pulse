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
      const [connData, empData] = await Promise.all([
        netsuiteApi.getCompanyConnections(),
        clientApi.listEmployees({ limit: 100 }),
      ])
      setConnections(connData || [])
      setCompanyEmployees(empData?.results ?? empData ?? [])
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
      addToast('Connection created. Complete OAuth to activate.', 'success')
      setShowForm(false)
      loadData()
    } catch (err) {
      addToast(err.payload?.message || err.message || 'Failed to create connection', 'error')
    } finally {
      setSaving(false)
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
                onTest={handleTest}
                onAssign={handleAssign}
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
            onClose={() => setAssigningId(null)}
            onAssigned={loadData}
          />
        )}

        <Toast toasts={toasts} removeToast={removeToast} />
      </div>
    </ClientLayout>
  )
}
