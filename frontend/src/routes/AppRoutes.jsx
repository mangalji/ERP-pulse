import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute.jsx'

import LoginPage from '../pages/auth/LoginPage.jsx'
import RegisterPage from '../pages/auth/RegisterPage.jsx'
import OtpVerificationPage from '../pages/auth/OtpVerificationPage.jsx'
import CompleteProfilePage from '../pages/auth/CompleteProfilePage.jsx'
import DashboardPage from '../pages/DashboardPage.jsx'
import ConnectNetSuitePage from '../pages/ConnectNetSuitePage.jsx'
import AiAssistantPage from '../pages/AiAssistantPage.jsx'
import CustomersPage from '../pages/CustomersPage.jsx'
import EmployeesPage from '../pages/EmployeesPage.jsx'
import VendorsPage from '../pages/VendorsPage.jsx'
import InventoryPage from '../pages/InventoryPage.jsx'
import SalesOrdersPage from '../pages/SalesOrdersPage.jsx'
import PurchaseOrdersPage from '../pages/PurchaseOrdersPage.jsx'
import InvoicesPage from '../pages/InvoicesPage.jsx'
import InvoiceReaderPage from '../pages/InvoiceReaderPage.jsx'
import ReportsPage from '../pages/ReportsPage.jsx'
import HistoryPage from '../pages/HistoryPage.jsx'
import ForgotPasswordPage from '../pages/auth/ForgotPasswordPage.jsx'
import ResetPasswordPage from '../pages/auth/ResetPasswordPage.jsx'
import SettingsPage from '../pages/SettingsPage.jsx'
import SystemHealthPage from '../pages/SystemHealthPage.jsx'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/otp-verification" element={<OtpVerificationPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/complete-profile" element={<CompleteProfilePage />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/connect-netsuite"
        element={
          <ProtectedRoute>
            <ConnectNetSuitePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ai-assistant"
        element={
          <ProtectedRoute>
            <AiAssistantPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customers"
        element={
          <ProtectedRoute>
            <CustomersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/employees"
        element={
          <ProtectedRoute>
            <EmployeesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/vendors"
        element={
          <ProtectedRoute>
            <VendorsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/inventory"
        element={
          <ProtectedRoute>
            <InventoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sales-orders"
        element={
          <ProtectedRoute>
            <SalesOrdersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/purchase-orders"
        element={
          <ProtectedRoute>
            <PurchaseOrdersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoices"
        element={
          <ProtectedRoute>
            <InvoicesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/invoice-reader"
        element={
          <ProtectedRoute>
            <InvoiceReaderPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <HistoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/system-health"
        element={
          <ProtectedRoute>
            <SystemHealthPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
