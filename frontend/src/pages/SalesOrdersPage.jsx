import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import EntityList from '../components/master-data/EntityList.jsx'
import EntityDetail from '../components/master-data/EntityDetail.jsx'
import { netsuiteApi } from '../services/netsuite.js'

const columns = [
  { key: 'tranId', label: 'Order #' },
  { key: 'entity', label: 'Customer', render: (value) => (value && typeof value === 'object' ? value.name : '--') },
  { key: 'status', label: 'Status' },
  { key: 'total', label: 'Total', render: (value) => (value != null ? `$${Number(value).toLocaleString('en-US')}` : '--') },
  { key: 'createdDate', label: 'Date' },
]

const detailFields = [
  { key: 'internalId', label: 'Internal ID' },
  { key: 'tranId', label: 'Order #' },
  { key: 'entity', label: 'Customer' },
  { key: 'status', label: 'Status' },
  { key: 'total', label: 'Total' },
  { key: 'createdDate', label: 'Date' },
  { key: 'lastModifiedDate', label: 'Last Modified' },
  { key: 'memo', label: 'Memo' },
]

export default function SalesOrdersPage() {
  const [selectedId, setSelectedId] = useState(null)

  return (
    <DashboardLayout title="Sales Orders">
      {selectedId ? (
        <EntityDetail
          fetchFn={netsuiteApi.getSalesOrder}
          recordId={selectedId}
          title="Sales Order Details"
          fields={detailFields}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <EntityList
          fetchFn={netsuiteApi.getSalesOrders}
          columns={columns}
          searchPlaceholder="Search sales orders..."
          title="All Sales Orders"
          onRowClick={(record) => setSelectedId(record.id)}
        />
      )}
    </DashboardLayout>
  )
}
