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

import SuperAdminDashboardPage from '../pages/superadmin/DashboardPage.jsx'
import SuperAdminCompaniesPage from '../pages/superadmin/CompaniesPage.jsx'
import SuperAdminPlansPage from '../pages/superadmin/PlansPage.jsx'
import SuperAdminModulesPage from '../pages/superadmin/ModulesPage.jsx'
import SuperAdminEmployeesPage from '../pages/superadmin/EmployeesPage.jsx'
import SuperAdminSupportSessionsPage from '../pages/superadmin/SupportSessionsPage.jsx'
import SuperAdminNotificationsPage from '../pages/superadmin/NotificationsPage.jsx'
import SuperAdminSettingsPage from '../pages/superadmin/SettingsPage.jsx'
import SuperAdminDemoRequestsPage from '../pages/superadmin/DemoRequestsPage.jsx'
import SuperAdminDemoRequestDetailPage from '../pages/superadmin/DemoRequestDetailPage.jsx'
import SuperAdminCompanySubscriptionPage from '../pages/superadmin/CompanySubscriptionPage.jsx'
import InvitationAcceptPage from '../pages/invitations/InvitationAcceptPage.jsx'

// Client Company Portal
import ClientDashboardPage from '../pages/client/DashboardPage.jsx'
import ClientInvoiceReaderPage from '../pages/client/InvoiceReaderPage.jsx'
import ClientOcrJobsPage from '../pages/client/OcrJobsPage.jsx'
import ClientAiAssistantPage from '../pages/client/AiAssistantPage.jsx'
import ClientEmployeesPage from '../pages/client/EmployeesPage.jsx'
import ClientReportsPage from '../pages/client/ReportsPage.jsx'
import ClientAnalyticsPage from '../pages/client/AnalyticsPage.jsx'
import ClientNotificationsPage from '../pages/client/NotificationsPage.jsx'
import ClientCompanySettingsPage from '../pages/client/CompanySettingsPage.jsx'
import ClientProfilePage from '../pages/client/ProfilePage.jsx'
import ClientSubscriptionPage from '../pages/client/SubscriptionPage.jsx'
import NetSuiteIntegrationsPage from '../pages/client/NetSuiteIntegrationsPage.jsx'
import EmployeeNetSuitePage from '../pages/client/EmployeeNetSuitePage.jsx'

// Executive BI Portal
import BIDashboardPage from '../pages/bi/DashboardPage.jsx'
import BiSalesAnalyticsPage from '../pages/bi/SalesAnalyticsPage.jsx'
import BiPurchaseAnalyticsPage from '../pages/bi/PurchaseAnalyticsPage.jsx'
import BiCustomerAnalyticsPage from '../pages/bi/CustomerAnalyticsPage.jsx'
import BiInventoryAnalyticsPage from '../pages/bi/InventoryAnalyticsPage.jsx'
import BiFinanceAnalyticsPage from '../pages/bi/FinanceAnalyticsPage.jsx'
import BiAiInsightsPage from '../pages/bi/AiInsightsPage.jsx'

// Reports Engine
import ReportsEngineDashboardPage from '../pages/reports-engine/ReportsDashboardPage.jsx'
import GenerateReportPage from '../pages/reports-engine/GenerateReportPage.jsx'
import ScheduledReportsPage from '../pages/reports-engine/ScheduledReportsPage.jsx'
import ReportHistoryPage from '../pages/reports-engine/ReportHistoryPage.jsx'
import TemplatesPage from '../pages/reports-engine/TemplatesPage.jsx'

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

      {/* AGSuite Super Admin Portal */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <SuperAdminDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/companies"
        element={
          <ProtectedRoute>
            <SuperAdminCompaniesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/plans"
        element={
          <ProtectedRoute>
            <SuperAdminPlansPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/modules"
        element={
          <ProtectedRoute>
            <SuperAdminModulesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/employees"
        element={
          <ProtectedRoute>
            <SuperAdminEmployeesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/support"
        element={
          <ProtectedRoute>
            <SuperAdminSupportSessionsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/notifications"
        element={
          <ProtectedRoute>
            <SuperAdminNotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <ProtectedRoute>
            <SuperAdminSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/demo-requests"
        element={
          <ProtectedRoute>
            <SuperAdminDemoRequestsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/demo-requests/:id"
        element={
          <ProtectedRoute>
            <SuperAdminDemoRequestDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/companies/:id/subscription"
        element={
          <ProtectedRoute>
            <SuperAdminCompanySubscriptionPage />
          </ProtectedRoute>
        }
      />

      {/* Invitation */}
      <Route path="/invitation/:token" element={<InvitationAcceptPage />} />

      {/* Client Company Portal */}
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <ClientDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/invoice-reader"
        element={
          <ProtectedRoute>
            <ClientInvoiceReaderPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ocr-jobs"
        element={
          <ProtectedRoute>
            <ClientOcrJobsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ai-assistant"
        element={
          <ProtectedRoute>
            <ClientAiAssistantPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/employees"
        element={
          <ProtectedRoute>
            <ClientEmployeesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports"
        element={
          <ProtectedRoute>
            <ClientReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/analytics"
        element={
          <ProtectedRoute>
            <ClientAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/notifications"
        element={
          <ProtectedRoute>
            <ClientNotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/settings"
        element={
          <ProtectedRoute>
            <ClientCompanySettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/profile"
        element={
          <ProtectedRoute>
            <ClientProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/subscription"
        element={
          <ProtectedRoute>
            <ClientSubscriptionPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/integrations/netsuite"
        element={
          <ProtectedRoute>
            <NetSuiteIntegrationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/netsuite"
        element={
          <ProtectedRoute>
            <EmployeeNetSuitePage />
          </ProtectedRoute>
        }
      />

{/* Executive BI Portal */}
      <Route
        path="/app/bi"
        element={
          <ProtectedRoute>
            <BIDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/sales"
        element={
          <ProtectedRoute>
            <BiSalesAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/purchase"
        element={
          <ProtectedRoute>
            <BiPurchaseAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/customers"
        element={
          <ProtectedRoute>
            <BiCustomerAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/inventory"
        element={
          <ProtectedRoute>
            <BiInventoryAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/finance"
        element={
          <ProtectedRoute>
            <BiFinanceAnalyticsPage />
          </ProtectedRoute>
        }
      />
<Route
        path="/app/bi/insights"
        element={
          <ProtectedRoute>
            <BiAiInsightsPage />
          </ProtectedRoute>
        }
      />

      {/* Reports Engine */}
      <Route
        path="/app/reports-engine"
        element={
          <ProtectedRoute>
            <ReportsEngineDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/generate"
        element={
          <ProtectedRoute>
            <GenerateReportPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/schedules"
        element={
          <ProtectedRoute>
            <ScheduledReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/history"
        element={
          <ProtectedRoute>
            <ReportHistoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/templates"
        element={
          <ProtectedRoute>
            <TemplatesPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
