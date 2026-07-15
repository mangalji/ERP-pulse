import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'entityId', label: 'Employee ID' },
  { key: 'firstName', label: 'First Name' },
  { key: 'lastName', label: 'Last Name' },
  { key: 'email', label: 'Email' },
  { key: 'title', label: 'Title' },
  { key: 'department', label: 'Department' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'entityId', label: 'Employee ID' },
  { key: 'firstName', label: 'First Name' },
  { key: 'lastName', label: 'Last Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'title', label: 'Title' },
  { key: 'department', label: 'Department' },
  { key: 'location', label: 'Location' },
  { key: 'isInactive', label: 'Inactive' },
]

export default function EmployeesPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Employees">
      {selectedId ? (
        <EntityDetail
          fetchFn={netsuiteApi.getEmployee}
          recordId={selectedId}
          title="Employee Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={netsuiteApi.getEmployees}
          columns={columns}
          searchPlaceholder="Search employees..."
          title="All Employees"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
