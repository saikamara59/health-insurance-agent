import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ClientListPage from './pages/ClientListPage'
import ClientProfilePage from './pages/ClientProfilePage'

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
            <Route index element={<ClientListPage />} />
            <Route path="clients/:id" element={<ClientProfilePage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
