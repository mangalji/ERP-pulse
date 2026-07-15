import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'tranId', label: 'PO #' },
  { key: 'entity', label: 'Vendor', render: (value) => (value && typeof value === 'object' ? value.name : '--') },
  { key: 'status', label: 'Status' },
  { key: 'total', label: 'Total', render: (value) => (value != null ? `$${Number(value).toLocaleString('en-US')}` : '--') },
  { key: 'createdDate', label: 'Date' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'tranId', label: 'PO #' },
  { key: 'entity', label: 'Vendor' },
  { key: 'status', label: 'Status' },
  { key: 'total', label: 'Total' },
  { key: 'createdDate', label: 'Date' },
  { key: 'lastModifiedDate', label: 'Last Modified' },
  { key: 'memo', label: 'Memo' },
]

export default function PurchaseOrdersPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Purchase Orders">
      {selectedId ? (
        <EntityDetail
          fetchFn={netsuiteApi.getPurchaseOrder}
          recordId={selectedId}
          title="Purchase Order Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={netsuiteApi.getPurchaseOrders}
          columns={columns}
          searchPlaceholder="Search purchase orders..."
          title="All Purchase Orders"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
