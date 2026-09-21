import { HashRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import AppRoutes from './routes/AppRoutes.jsx'

/**
 * Root application component.
 * HashRouter is used for Zoho Catalyst Web Client compatibility so direct links and page refreshes work smoothly.
 */
function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </HashRouter>
  )
}

export default App
