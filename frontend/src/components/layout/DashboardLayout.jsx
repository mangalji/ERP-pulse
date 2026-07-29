import { useState } from 'react'
import Sidebar from './Sidebar.jsx'
import TopNav from './TopNav.jsx'
import Footer from './Footer.jsx'

/** Shell used by every authenticated page: sidebar + top nav + content + footer. */
export default function DashboardLayout({ title, children, fullHeight }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-[var(--color-canvas)]">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav title={title} onMenuClick={() => setSidebarOpen(true)} />
        <main className={`flex-1 ${fullHeight ? 'p-0' : 'px-4 py-6 sm:px-6 lg:px-8'}`}>{children}</main>
        <Footer />
      </div>
    </div>
  )
}
