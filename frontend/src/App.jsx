import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
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
import CoverageTranslatorPage from './pages/CoverageTranslatorPage'
import TemporalPlanPage from './pages/TemporalPlanPage'
import CostCalculatorPage from './pages/CostCalculatorPage'
import OnboardingSuccessPage from './pages/OnboardingSuccessPage'
import FeedbackDashboardPage from './pages/FeedbackDashboardPage'
import AdminPage from './pages/AdminPage'
import AdminRoute from './components/AdminRoute'

// At `/`, show the public marketing page to logged-out visitors; redirect
// authenticated users into their workspace so they don't see a sales pitch
// every time they hit the root URL.
function HomeGate() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <HomePage />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<HomeGate />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="clients" element={<ClientListPage />} />
            <Route path="clients/new" element={<AddClientPage />} />
            <Route path="clients/success" element={<OnboardingSuccessPage />} />
            <Route path="clients/:id" element={<ClientProfilePage />} />
            <Route path="compare" element={<PlanComparisonPage />} />
            <Route path="network" element={<NetworkVerificationPage />} />
            <Route path="translator" element={<CoverageTranslatorPage />} />
            <Route path="plan" element={<TemporalPlanPage />} />
            <Route path="calculator" element={<CostCalculatorPage />} />
            <Route path="appeals" element={<ClaimsAppealPage />} />
            <Route path="history" element={<ComparisonHistoryPage />} />
            <Route path="leads" element={<LeadsPage />} />
            <Route path="feedback" element={<FeedbackDashboardPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="support" element={<SupportPage />} />
            <Route
              path="admin"
              element={
                <AdminRoute>
                  <AdminPage />
                </AdminRoute>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
