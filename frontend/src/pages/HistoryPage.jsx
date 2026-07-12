import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import Card from '../components/ui/Card.jsx'
import TimelineItem from '../components/history/TimelineItem.jsx'
import { historyTimeline } from '../constants/dummyData.js'

export default function HistoryPage() {
  return (
    <DashboardLayout title="History">
      <Card className="max-w-2xl p-6">
        {historyTimeline.map((item, index) => (
          <TimelineItem key={item.id} item={item} isLast={index === historyTimeline.length - 1} />
        ))}
      </Card>
    </DashboardLayout>
  )
}
