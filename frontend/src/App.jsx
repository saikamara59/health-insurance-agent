import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ClientListPage from './pages/ClientListPage'
import ClientProfilePage from './pages/ClientProfilePage'
import AddClientPage from './pages/AddClientPage'
import SettingsPage from './pages/SettingsPage'
import LeadsPage from './pages/LeadsPage'
import SupportPage from './pages/SupportPage'
import ActivityPage from './pages/ActivityPage'
import AnalyticsPage from './pages/AnalyticsPage'
import ClaimsAppealPage from './pages/ClaimsAppealPage'
import ComparisonHistoryPage from './pages/ComparisonHistoryPage'
import PlanComparisonPage from './pages/PlanComparisonPage'
import NetworkVerificationPage from './pages/NetworkVerificationPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="clients" element={<ClientListPage />} />
            <Route path="clients/new" element={<AddClientPage />} />
            <Route path="clients/:id" element={<ClientProfilePage />} />
            <Route path="leads" element={<LeadsPage />} />
            <Route path="compare" element={<PlanComparisonPage />} />
            <Route path="network" element={<NetworkVerificationPage />} />
            <Route path="history" element={<ComparisonHistoryPage />} />
            <Route path="appeals" element={<ClaimsAppealPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="support" element={<SupportPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
