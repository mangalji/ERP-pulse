import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'
import ModuleProtectedRoute from './ModuleProtectedRoute.jsx'
import PublicLayout from '../components/layout/PublicLayout.jsx'

import LoginPage from '../pages/auth/LoginPage.jsx'
import OtpVerificationPage from '../pages/auth/OtpVerificationPage.jsx'
import ForgotPasswordPage from '../pages/auth/ForgotPasswordPage.jsx'
import ResetPasswordPage from '../pages/auth/ResetPasswordPage.jsx'

import SuperAdminDashboardPage from '../pages/superadmin/DashboardPage.jsx'
import SuperAdminCompaniesPage from '../pages/superadmin/CompaniesPage.jsx'
import SuperAdminPlansPage from '../pages/superadmin/PlansPage.jsx'
import SuperAdminPlanDetailPage from '../pages/superadmin/PlanDetailPage.jsx'
import SuperAdminEmployeesPage from '../pages/superadmin/EmployeesPage.jsx'
import SuperAdminSettingsPage from '../pages/superadmin/SettingsPage.jsx'
import SuperAdminCompanyDetailPage from '../pages/superadmin/CompanyDetailPage.jsx'
import SuperAdminCompanySubscriptionPage from '../pages/superadmin/CompanySubscriptionPage.jsx'
import InvitationAcceptPage from '../pages/invitations/InvitationAcceptPage.jsx'

// Public Website
import PublicHomePage from '../pages/public/HomePage.jsx'

// Client Company Portal
import ClientDashboardPage from '../pages/client/DashboardPage.jsx'
import ClientEmployeesPage from '../pages/client/EmployeesPage.jsx'
import ClientCompanySettingsPage from '../pages/client/CompanySettingsPage.jsx'
import CenterTabsPage from '../pages/client/CenterTabsPage.jsx'
import CenterCategoriesPage from '../pages/client/CenterCategoriesPage.jsx'
import CenterTabDetailPage from '../pages/client/CenterTabDetailPage.jsx'
import CenterCategoryDetailPage from '../pages/client/CenterCategoryDetailPage.jsx'
import ClientProfilePage from '../pages/client/ProfilePage.jsx'
import ClientSubscriptionPage from '../pages/client/SubscriptionPage.jsx'
import NetSuiteIntegrationsPage from '../pages/client/NetSuiteIntegrationsPage.jsx'
import EmployeeNetSuitePage from '../pages/client/EmployeeNetSuitePage.jsx'
import TransactionsPage from '../pages/client/TransactionsPage.jsx'
import ProductsPage from '../pages/client/ProductsPage.jsx'

import OcrTestPage from '../pages/client/OcrTestPage.jsx'
import OcrFieldMappingPage from '../pages/client/OcrFieldMappingPage.jsx'
import OcrTestResultPage from '../pages/client/OcrTestResultPage.jsx'
import OcrBatchHistoryPage from '../pages/client/OcrBatchHistoryPage.jsx'
/* Legacy flat pages (DashboardLayout) — retained on disk per DEVELOPMENT_GUIDELINES.md.
 * These pages are NOT routed; their legacy URLs redirect to /app/* equivalents.
 * Commented imports kept for traceability. Do not delete files.
 */

function PublicRoute({ children }) {
  return <PublicLayout>{children}</PublicLayout>
}
function CompanyAdminRoute({ children }) {
  const { user } = useAuth()

  const isCompanyAdmin =
    user?.is_superuser ||
    user?.is_staff ||
    (user?.roles || []).some(
      (role) => String(role).toLowerCase() === 'company_admin'
    )

  if (!isCompanyAdmin) {
    return <Navigate to="/app/settings" replace />
  }

  return children
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
      <Route path="/employees" element={<Navigate to="/app/employees" replace />} />
      <Route path="/history" element={<Navigate to="/app" replace />} />
      <Route path="/settings" element={<Navigate to="/app/settings" replace />} />
      <Route path="/system-health" element={<Navigate to="/app" replace />} />

      {/* Single transaction page; DB menu supplies the view query param. */}
      <Route path="/app/transactions" element={
        <ProtectedRoute requiredRole="client">
          <TransactionsPage />
        </ProtectedRoute>
      } />

      <Route path="/app/products" element={
        <ProtectedRoute requiredRole="client">
          <ProductsPage />
        </ProtectedRoute>
      } />


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
        path="/admin/employees"
        element={
          <ProtectedRoute requiredRole="admin">
            <SuperAdminEmployeesPage />
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
        path="/app/ocr-test/field-mapping"
        element={
          <ProtectedRoute requiredRole="client">
            <OcrFieldMappingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ocr-test"
        element={
          <ProtectedRoute requiredRole="client">
            <OcrTestPage />
          </ProtectedRoute>
        }
      />
      <Route
  path="/app/ocr-test/history/batch/:batchId"
  element={
    <ProtectedRoute requiredRole="client">
      <OcrBatchHistoryPage />
    </ProtectedRoute>
  }
/>

<Route
  path="/app/ocr-test/history/:documentId"
  element={
    <ProtectedRoute requiredRole="client">
      <OcrTestResultPage />
    </ProtectedRoute>
  }
/>
      <Route
  path="/app/ocr-test/result"
  element={
    <ProtectedRoute requiredRole="client">
      <OcrTestResultPage />
    </ProtectedRoute>
  }
/>
<Route path="/app/ocr-test/history/:documentId" element={<OcrTestResultPage />} />

      <Route
        path="/app/employees"
        element={
            <ClientEmployeesPage />
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
          path="/app/settings/customize/center-categories"
          element={
            <ProtectedRoute requiredRole="client">
              <CenterCategoriesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/app/settings/customize/center-categories/:categoryId"
          element={
            <ProtectedRoute requiredRole="client">
              <CenterCategoryDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/app/settings/customize/center-tabs"
          element={
            <ProtectedRoute requiredRole="client">
              <CenterTabsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/app/settings/customize/center-tabs/:tabId"
          element={
            <ProtectedRoute requiredRole="client">
              <CenterTabDetailPage />
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
      {/* Catch-all: route to portal if authenticated, login if not */}
      <Route path="*" element={<CatchAllRoute />} />
    </Routes>
  )
}