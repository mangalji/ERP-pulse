/**
 * Dummy data for UI-only development. Nothing here is fetched from the
 * backend — this task explicitly excludes API integration. Replace with
 * real service calls once the corresponding API exists.
 */

export const kpiSummary = [
  { id: 'revenue', label: 'Revenue (MTD)', value: 482_600, delta: 14.2, format: 'currency' },
  { id: 'profit', label: 'Profit (MTD)', value: 87_400, delta: 6.8, format: 'currency' },
  { id: 'orders', label: 'Orders', value: 421, delta: -3.1, format: 'number' },
  { id: 'health', label: 'Business Health', value: 82, delta: 4, format: 'score' },
]

export const revenueTrend = [42, 48, 45, 51, 55, 53, 60, 58, 64, 61, 68, 72]

export const topCustomers = [
  { id: 1, name: 'Meridian Manufacturing', value: 148_200, share: 31 },
  { id: 2, name: 'Northwind Traders', value: 96_500, share: 20 },
  { id: 3, name: 'Blue Harbor Logistics', value: 61_300, share: 13 },
  { id: 4, name: 'Fenwick & Co.', value: 44_900, share: 9 },
]

export const recentActivity = [
  { id: 1, type: 'sync', text: 'NetSuite sync completed — 214 records updated', time: '12 min ago' },
  { id: 2, type: 'ai', text: 'AI Assistant generated "Q2 Revenue Summary"', time: '1 hour ago' },
  { id: 3, type: 'report', text: 'Monthly report exported as PDF', time: '3 hours ago' },
  { id: 4, type: 'sync', text: 'NetSuite sync completed — 98 records updated', time: 'Yesterday' },
]

export const suggestedPrompts = [
  'Summarize this month\u2019s revenue performance',
  'Which customers are at risk of churning?',
  'Show me my top 5 products by margin',
  'Explain the drop in order volume last week',
]

export const chatHistoryPreview = [
  {
    id: 1,
    role: 'assistant',
    text: 'Revenue is up 14% month-over-month, driven mainly by Meridian Manufacturing\u2019s renewed contract. Profit margin held steady at 18%.',
  },
]

export const reportsList = [
  { id: 1, title: 'Executive Summary — June 2026', type: 'Executive', date: 'Jul 1, 2026' },
  { id: 2, title: 'Customer Performance Report', type: 'Customer', date: 'Jun 28, 2026' },
  { id: 3, title: 'Product Margin Analysis', type: 'Product', date: 'Jun 21, 2026' },
  { id: 4, title: 'Monthly Business Review — May', type: 'Executive', date: 'Jun 2, 2026' },
]

export const historyTimeline = [
  { id: 1, kind: 'ai', title: 'Asked: "Why did profit drop in April?"', date: 'Jul 10, 2026' },
  { id: 2, kind: 'report', title: 'Generated: Customer Performance Report', date: 'Jun 28, 2026' },
  { id: 3, kind: 'ai', title: 'Asked: "Summarize top products this quarter"', date: 'Jun 24, 2026' },
  { id: 4, kind: 'report', title: 'Generated: Product Margin Analysis', date: 'Jun 21, 2026' },
  { id: 5, kind: 'ai', title: 'Asked: "Which customers grew fastest in Q1?"', date: 'Jun 15, 2026' },
]
