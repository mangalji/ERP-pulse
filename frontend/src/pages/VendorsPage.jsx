import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'entityId', label: 'Vendor ID' },
  { key: 'companyName', label: 'Company' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'status', label: 'Status' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'entityId', label: 'Vendor ID' },
  { key: 'companyName', label: 'Company Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'currency', label: 'Currency' },
  { key: 'status', label: 'Status' },
  { key: 'addressbook', label: 'Addresses' },
]

export default function VendorsPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Vendors">
      {selectedId ? (
        <EntityDetail
          fetchFn={netsuiteApi.getVendor}
          recordId={selectedId}
          title="Vendor Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={netsuiteApi.getVendors}
          columns={columns}
          searchPlaceholder="Search vendors..."
          title="All Vendors"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
