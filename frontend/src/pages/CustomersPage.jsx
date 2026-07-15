import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'entityId', label: 'Customer ID' },
  { key: 'companyName', label: 'Company' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'status', label: 'Status' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'entityId', label: 'Customer ID' },
  { key: 'companyName', label: 'Company Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'currency', label: 'Currency' },
  { key: 'status', label: 'Status' },
  { key: 'addressbook', label: 'Addresses' },
]

export default function CustomersPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Customers">
      {selectedId ? (
        <EntityDetail
          fetchFn={netsuiteApi.getCustomer}
          recordId={selectedId}
          title="Customer Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={netsuiteApi.getCustomers}
          columns={columns}
          searchPlaceholder="Search customers..."
          title="All Customers"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
