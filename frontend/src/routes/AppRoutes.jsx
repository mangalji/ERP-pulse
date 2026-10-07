import { lazy, Suspense, useEffect, useRef } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'
import PublicLayout from '../components/layout/PublicLayout.jsx'
import PublicHomePage from '../pages/public/HomePage.jsx'

// Route-level lazy loading keeps page-specific JavaScript out of the initial bundle.
const LoginPage = lazy(() => import('../pages/auth/LoginPage.jsx'))
const OtpVerificationPage = lazy(() => import('../pages/auth/OtpVerificationPage.jsx'))
const ForgotPasswordPage = lazy(() => import('../pages/auth/ForgotPasswordPage.jsx'))
const ResetPasswordPage = lazy(() => import('../pages/auth/ResetPasswordPage.jsx'))

const SuperAdminDashboardPage = lazy(() => import('../pages/superadmin/DashboardPage.jsx'))
const SuperAdminCompaniesPage = lazy(() => import('../pages/superadmin/CompaniesPage.jsx'))
const SuperAdminPlansPage = lazy(() => import('../pages/superadmin/PlansPage.jsx'))
const SuperAdminPlanDetailPage = lazy(() => import('../pages/superadmin/PlanDetailPage.jsx'))
const SuperAdminEmployeesPage = lazy(() => import('../pages/superadmin/EmployeesPage.jsx'))
const SuperAdminSettingsPage = lazy(() => import('../pages/superadmin/SettingsPage.jsx'))
const SuperAdminCompanyDetailPage = lazy(() => import('../pages/superadmin/CompanyDetailPage.jsx'))
const SuperAdminCompanySubscriptionPage = lazy(() => import('../pages/superadmin/CompanySubscriptionPage.jsx'))
const InvitationAcceptPage = lazy(() => import('../pages/invitations/InvitationAcceptPage.jsx'))
const AIIntegrationPage = lazy(() => import('../pages/client/AIIntegrationPage.jsx'))


// Client Company Portal
const ClientDashboardPage = lazy(() => import('../pages/client/DashboardPage.jsx'))
const ClientEmployeesPage = lazy(() => import('../pages/client/EmployeesPage.jsx'))
const ClientCompanySettingsPage = lazy(() => import('../pages/client/CompanySettingsPage.jsx'))
const CenterTabsPage = lazy(() => import('../pages/client/CenterTabsPage.jsx'))
const CenterCategoriesPage = lazy(() => import('../pages/client/CenterCategoriesPage.jsx'))
const CenterTabDetailPage = lazy(() => import('../pages/client/CenterTabDetailPage.jsx'))
const CenterCategoryDetailPage = lazy(() => import('../pages/client/CenterCategoryDetailPage.jsx'))
const ClientProfilePage = lazy(() => import('../pages/client/ProfilePage.jsx'))
const ClientSubscriptionPage = lazy(() => import('../pages/client/SubscriptionPage.jsx'))
const NetSuiteIntegrationsPage = lazy(() => import('../pages/client/NetSuiteIntegrationsPage.jsx'))
const EmployeeNetSuitePage = lazy(() => import('../pages/client/EmployeeNetSuitePage.jsx'))
const TransactionsPage = lazy(() => import('../pages/client/TransactionsPage.jsx'))
const OcrPage = lazy(() => import('../pages/client/OcrPage.jsx'))
const OcrResultPage = lazy(() => import('../pages/client/OcrResultPage.jsx'))
const OcrBatchHistoryPage = lazy(() => import('../pages/client/OcrBatchHistoryPage.jsx'))
const DataExtractionHistoryPage = lazy(() => import('../pages/client/DataExtractionHistoryPage.jsx'))
const FileTemplatePage = lazy(() => import('../pages/client/FileTemplatePage.jsx'))

function PublicRoute({ children }) {
  return <PublicLayout>{children}</PublicLayout>
}

function CatchAllRoute() {
  const { isAuthenticated, isSuperAdmin } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <Navigate to={isSuperAdmin ? '/admin' : '/app'} replace />
}

function RouteLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-label="Loading page">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-primary)]" />
    </div>
  )
}
const OCR_SESSION_KEYS = [
  'ocr_test_result',
]

function clearOcrWorkflowSession() {
  OCR_SESSION_KEYS.forEach((key) => {
    sessionStorage.removeItem(key)
  })
}
const OCR_DATA_EXTRACTION_ROUTE = '/app/ocr'

export default function AppRoutes() {
  const location = useLocation()
  const previousPathRef = useRef(location.pathname)
  useEffect(() => {
   const previousPath = previousPathRef.current
   const currentPath = location.pathname
    
    /*
     * Entering Data Extraction from another page:
     * always start with a fresh OCR workflow.
     *
     * Refreshing Data Extraction itself does NOT clear anything because
     * previousPath === currentPath in that case.
     */
    if (
      currentPath === OCR_DATA_EXTRACTION_ROUTE &&
      previousPath !== OCR_DATA_EXTRACTION_ROUTE
    ) {
      clearOcrWorkflowSession()
    }

    previousPathRef.current = currentPath
  }, [location.pathname]) 
   /*
   * If the user reaches this route through browser Back/Forward or an old
   * history entry after the workflow has already been cleared, never render
   */
  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes 
      location={location}
      key={location.state?.__refreshKey ?? 'app-routes'}
      >
      {/* Public Website */}
      <Route path="/" element={<PublicRoute><PublicHomePage /></PublicRoute>} />

      {/* Authentication */}
      <Route path="/login" element={<LoginPage />} />
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
        path="/app/ocr/history"
        element={
          <ProtectedRoute requiredRole="client">
            <DataExtractionHistoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/ocr"
        element={
          <ProtectedRoute requiredRole="client">
            <OcrPage />
          </ProtectedRoute>
        }
      />
      <Route path="/app/ocr/history/batch/:batchId" 
        element={
          <ProtectedRoute requiredRole="client">
            <OcrBatchHistoryPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/app/ocr/history/:documentId"
        element={
          <ProtectedRoute requiredRole="client">
            <OcrResultPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/app/ocr/file-template"
        element={
          <ProtectedRoute requiredRole="client">
            <FileTemplatePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/app/ocr/result"
        element={
          <ProtectedRoute requiredRole="client">
            <OcrResultPage />
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
        path="/app/settings"
        element={
          <ProtectedRoute requiredRole="client">
            <ClientCompanySettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/settings/ai-integration"
        element={
          <ProtectedRoute requiredRole="client">
            <AIIntegrationPage />
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
    </Suspense>
  )
}