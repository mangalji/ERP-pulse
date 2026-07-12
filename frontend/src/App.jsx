import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import AppRoutes from './routes/AppRoutes.jsx'

/**
 * Root application component. Frontend UI only — no API integration yet.
 * AuthProvider holds local, dummy auth state so routes can be gated
 * during frontend development; it makes no backend calls.
 */
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
