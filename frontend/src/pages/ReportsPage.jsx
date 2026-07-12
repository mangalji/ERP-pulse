import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import ReportCard from '../components/reports/ReportCard.jsx'
import { reportsList } from '../constants/dummyData.js'

export default function ReportsPage() {
  return (
    <DashboardLayout title="Reports">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {reportsList.map((report) => (
          <ReportCard key={report.id} report={report} />
        ))}
      </div>
    </DashboardLayout>
  )
}
