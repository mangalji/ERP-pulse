import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'itemId', label: 'Item ID' },
  { key: 'displayName', label: 'Name' },
  { key: 'vendorName', label: 'Vendor' },
  { key: 'cost', label: 'Cost', render: (value) => (value != null ? `$${Number(value).toLocaleString('en-US')}` : '--') },
  { key: 'type', label: 'Type' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'itemId', label: 'Item ID' },
  { key: 'displayName', label: 'Display Name' },
  { key: 'vendorName', label: 'Vendor Name' },
  { key: 'cost', label: 'Cost' },
  { key: 'type', label: 'Type' },
  { key: 'matrix', label: 'Matrix' },
  { key: 'isInactive', label: 'Inactive' },
]

export default function InventoryPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Inventory">
      {selectedId ? (
        <EntityDetail
          fetchFn={(id) => netsuiteApi.getItem(id, 'inventoryItem')}
          recordId={selectedId}
          title="Inventory Item Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={(params) => netsuiteApi.getItems('inventoryItem', params)}
          columns={columns}
          searchPlaceholder="Search inventory..."
          title="Inventory Items"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
