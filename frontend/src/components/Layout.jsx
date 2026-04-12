import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="flex-1 md:ml-64 min-h-screen">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <div className="pt-24 pb-12 px-4 sm:px-6 md:px-10 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
