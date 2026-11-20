import { HashRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import AppRoutes from './routes/AppRoutes.jsx'

/**
 * Root application component.
 * HashRouter keeps direct links and page refreshes working across static hosts.
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
