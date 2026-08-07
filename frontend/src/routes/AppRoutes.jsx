import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'
import PublicLayout from '../components/layout/PublicLayout.jsx'

import LoginPage from '../pages/auth/LoginPage.jsx'
import OtpVerificationPage from '../pages/auth/OtpVerificationPage.jsx'
import ForgotPasswordPage from '../pages/auth/ForgotPasswordPage.jsx'
import ResetPasswordPage from '../pages/auth/ResetPasswordPage.jsx'

import SuperAdminDashboardPage from '../pages/superadmin/DashboardPage.jsx'
import SuperAdminCompaniesPage from '../pages/superadmin/CompaniesPage.jsx'
import SuperAdminPlansPage from '../pages/superadmin/PlansPage.jsx'
import SuperAdminPlanDetailPage from '../pages/superadmin/PlanDetailPage.jsx'
import SuperAdminModulesPage from '../pages/superadmin/ModulesPage.jsx'
import SuperAdminEmployeesPage from '../pages/superadmin/EmployeesPage.jsx'
import SuperAdminSupportSessionsPage from '../pages/superadmin/SupportSessionsPage.jsx'
import SuperAdminNotificationsPage from '../pages/superadmin/NotificationsPage.jsx'
import SuperAdminSettingsPage from '../pages/superadmin/SettingsPage.jsx'
import SuperAdminDemoRequestsPage from '../pages/superadmin/DemoRequestsPage.jsx'
import SuperAdminDemoRequestDetailPage from '../pages/superadmin/DemoRequestDetailPage.jsx'
import SuperAdminCompanyDetailPage from '../pages/superadmin/CompanyDetailPage.jsx'
import SuperAdminCompanySubscriptionPage from '../pages/superadmin/CompanySubscriptionPage.jsx'
import InvitationAcceptPage from '../pages/invitations/InvitationAcceptPage.jsx'

// Public Website
import PublicHomePage from '../pages/public/HomePage.jsx'
import PublicFeaturesPage from '../pages/public/FeaturesPage.jsx'
import PublicPricingPage from '../pages/public/PricingPage.jsx'
import PublicAboutPage from '../pages/public/AboutPage.jsx'
import PublicContactPage from '../pages/public/ContactPage.jsx'
import PublicRequestDemoPage from '../pages/public/RequestDemoPage.jsx'

// Client Company Portal
import ClientDashboardPage from '../pages/client/DashboardPage.jsx'
import ClientInvoiceReaderPage from '../pages/client/InvoiceReaderPage.jsx'
import ClientInvoiceDetailPage from '../pages/client/InvoiceDetailPage.jsx'
import ClientPayloadPreviewPage from '../pages/client/PayloadPreviewPage.jsx'
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

/* Legacy flat pages (DashboardLayout) — retained on disk per DEVELOPMENT_GUIDELINES.md.
 * These pages are NOT routed; their legacy URLs redirect to /app/* equivalents.
 * Commented imports kept for traceability. Do not delete files.
 */
// import DashboardPage from '../pages/DashboardPage.jsx'
// import ConnectNetSuitePage from '../pages/ConnectNetSuitePage.jsx'
// import AiAssistantPage from '../pages/AiAssistantPage.jsx'
// import CustomersPage from '../pages/CustomersPage.jsx'
// import EmployeesPage from '../pages/EmployeesPage.jsx'
// import VendorsPage from '../pages/VendorsPage.jsx'
// import InventoryPage from '../pages/InventoryPage.jsx'
// import SalesOrdersPage from '../pages/SalesOrdersPage.jsx'
// import PurchaseOrdersPage from '../pages/PurchaseOrdersPage.jsx'
// import InvoicesPage from '../pages/InvoicesPage.jsx'
// import InvoiceReaderPage from '../pages/InvoiceReaderPage.jsx'
// import ReportsPage from '../pages/ReportsPage.jsx'
// import HistoryPage from '../pages/HistoryPage.jsx'
// import SettingsPage from '../pages/SettingsPage.jsx'
// import SystemHealthPage from '../pages/SystemHealthPage.jsx'

/* Legacy auth pages — intentionally not routed (Sprint 8.4: invitation-only onboarding). */
// import RegisterPage from '../pages/auth/RegisterPage.jsx'
// import CompleteProfilePage from '../pages/auth/CompleteProfilePage.jsx'

function PublicRoute({ children }) {
  return <PublicLayout>{children}</PublicLayout>
}

function CatchAllRoute() {
  const { isAuthenticated, isSuperAdmin } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <Navigate to={isSuperAdmin ? '/admin' : '/app'} replace />
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public Website */}
      <Route path="/" element={<PublicRoute><PublicHomePage /></PublicRoute>} />
      <Route path="/features" element={<PublicRoute><PublicFeaturesPage /></PublicRoute>} />
      <Route path="/pricing" element={<PublicRoute><PublicPricingPage /></PublicRoute>} />
      <Route path="/about" element={<PublicRoute><PublicAboutPage /></PublicRoute>} />
      <Route path="/contact" element={<PublicRoute><PublicContactPage /></PublicRoute>} />
      <Route path="/request-demo" element={<PublicRoute><PublicRequestDemoPage /></PublicRoute>} />

      {/* Authentication */}
      <Route path="/login" element={<LoginPage />} />
      {/*
        LEGACY (Sprint 8.4): public registration retired in favor of
        invitation-only onboarding. RegisterPage.jsx and CompleteProfilePage.jsx
        remain on disk per DEVELOPMENT_GUIDELINES.md ("never delete files")
        but are intentionally not routed here, so they are unreachable from
        the UI. Do not re-add these routes without a product decision.
      */}
      <Route path="/otp-verification" element={<OtpVerificationPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Legacy redirects → new client portal routes */}
      <Route path="/dashboard" element={<Navigate to="/app" replace />} />
      <Route path="/connect-netsuite" element={<Navigate to="/app/integrations/netsuite" replace />} />
      <Route path="/ai-assistant" element={<Navigate to="/app/ai-assistant" replace />} />
      <Route path="/customers" element={<Navigate to="/app/bi/customers" replace />} />
      <Route path="/employees" element={<Navigate to="/app/employees" replace />} />
      <Route path="/vendors" element={<Navigate to="/app" replace />} />
      <Route path="/inventory" element={<Navigate to="/app/bi/inventory" replace />} />
      <Route path="/sales-orders" element={<Navigate to="/app/bi/sales" replace />} />
      <Route path="/purchase-orders" element={<Navigate to="/app/bi/purchase" replace />} />
      <Route path="/invoices" element={<Navigate to="/app/invoice-reader" replace />} />
      <Route path="/invoice-reader" element={<Navigate to="/app/invoice-reader" replace />} />
      <Route path="/reports" element={<Navigate to="/app/reports" replace />} />
      <Route path="/history" element={<Navigate to="/app" replace />} />
      <Route path="/settings" element={<Navigate to="/app/settings" replace />} />
      <Route path="/system-health" element={<Navigate to="/app" replace />} />

      {/* AGSuite Super Admin Portal */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/companies"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminCompaniesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/plans"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminPlansPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/plans/:id"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminPlanDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/modules"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminModulesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/employees"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminEmployeesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/support"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminSupportSessionsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/notifications"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminNotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/demo-requests"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminDemoRequestsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/demo-requests/:id"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminDemoRequestDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/companies/:id"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminCompanyDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/companies/:id/subscription"
        element={
          <ProtectedRoute requiredRole="admin">
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
          <ProtectedRoute requiredRole="client">
            <ClientDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/invoice-reader"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientInvoiceReaderPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/invoice-reader/:id"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientInvoiceDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/invoice-reader/:id/payload"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientPayloadPreviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ocr-jobs"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientOcrJobsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ai-assistant"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientAiAssistantPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/employees"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientEmployeesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/analytics"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/notifications"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientNotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/settings"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientCompanySettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/profile"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/subscription"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientSubscriptionPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/integrations/netsuite"
        element={
          <ProtectedRoute requiredRole="client">
            <NetSuiteIntegrationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/netsuite"
        element={
          <ProtectedRoute requiredRole="client">
            <EmployeeNetSuitePage />
          </ProtectedRoute>
        }
      />

      {/* Executive BI Portal */}
      <Route
        path="/app/bi"
        element={
          <ProtectedRoute requiredRole="client">
            <BIDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/sales"
        element={
          <ProtectedRoute requiredRole="client">
            <BiSalesAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/purchase"
        element={
          <ProtectedRoute requiredRole="client">
            <BiPurchaseAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/customers"
        element={
          <ProtectedRoute requiredRole="client">
            <BiCustomerAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/inventory"
        element={
          <ProtectedRoute requiredRole="client">
            <BiInventoryAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/finance"
        element={
          <ProtectedRoute requiredRole="client">
            <BiFinanceAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/bi/insights"
        element={
          <ProtectedRoute requiredRole="client">
            <BiAiInsightsPage />
          </ProtectedRoute>
        }
      />

      {/* Reports Engine */}
      <Route
        path="/app/reports-engine"
        element={
          <ProtectedRoute requiredRole="client">
            <ReportsEngineDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/generate"
        element={
          <ProtectedRoute requiredRole="client">
            <GenerateReportPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/schedules"
        element={
          <ProtectedRoute requiredRole="client">
            <ScheduledReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/history"
        element={
          <ProtectedRoute requiredRole="client">
            <ReportHistoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/reports-engine/templates"
        element={
          <ProtectedRoute requiredRole="client">
            <TemplatesPage />
          </ProtectedRoute>
        }
      />

      {/* Catch-all: route to portal if authenticated, login if not */}
      <Route path="*" element={<CatchAllRoute />} />
    </Routes>
  )
}
