import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import NotificationPanel from './NotificationPanel';
import Tweaks from './ui/Tweaks';

export const LayoutContext = { sidebarOpen: false };

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  return (
    <div className="app">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="main">
        <Outlet context={{
          openMenu: () => setSidebarOpen(true),
          openNotifications: () => setNotificationsOpen(true),
        }} />
      </div>
      {notificationsOpen && <NotificationPanel open={notificationsOpen} onClose={() => setNotificationsOpen(false)} />}
      <Tweaks />
    </div>
  );
}
