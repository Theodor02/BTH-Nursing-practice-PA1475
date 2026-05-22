import './App.css'
import { useEffect, useState, type ReactNode } from 'react'
import { HashRouter as Router, Routes, Route, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { DarkModeProvider } from './context/DarkModeContext'
import { LeaveGuardProvider } from "./context/leaveGuardContext"
import Header from './components/Header'
import Login from './pages/login'
import History from './pages/history'

import Questionselect from './pages/questionselect'
import Questions from './pages/questions'
import Index from './pages/index'
import Control from './pages/controlpanel'
import {
  canAccessControlPanel,
  getCurrentBackendUser,
  getSignedInAccount,
  hasBackendSession,
} from './services/entraAuth'
import ResultOverlay from './components/ResultOverlay'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [hasSession, setHasSession] = useState(false)

  useEffect(() => {
    let isMounted = true

    const checkSession = async () => {
      try {
        const account = await getSignedInAccount()
        if (!account) {
          if (isMounted) {
            setHasSession(false)
          }
          return
        }

        const backendSessionExists = await hasBackendSession()
        if (isMounted) {
          setHasSession(backendSessionExists)
        }
      } catch {
        if (isMounted) {
          setHasSession(false)
        }
      } finally {
        if (isMounted) {
          setIsCheckingSession(false)
        }
      }
    }

    void checkSession()

    return () => {
      isMounted = false
    }
  }, [])

  if (isCheckingSession) {
    return null
  }

  if (!hasSession) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function ProtectedShell() {
  return (
    <ProtectedRoute>
      <Header />
      <Outlet />
    </ProtectedRoute>
  )
}

function ControlPanelRoute({ children }: { children: ReactNode }) {
  const [isCheckingRole, setIsCheckingRole] = useState(true)
  const [canAccess, setCanAccess] = useState(false)

  useEffect(() => {
    let isMounted = true

    const checkRole = async () => {
      try {
        const user = await getCurrentBackendUser()
        if (isMounted) {
          setCanAccess(Boolean(user?.can_access_control_panel || canAccessControlPanel(user?.role)))
        }
      } catch {
        if (isMounted) {
          setCanAccess(false)
        }
      } finally {
        if (isMounted) {
          setIsCheckingRole(false)
        }
      }
    }

    void checkRole()

    return () => {
      isMounted = false
    }
  }, [])

  if (isCheckingRole) {
    return null
  }

  if (!canAccess) {
    return <Navigate to="/home" replace />
  }

  return <>{children}</>
}

function SessionExpiredGuard() {
  const navigate = useNavigate();

  useEffect(() => {
    function onSessionExpired() {
      navigate("/", { replace: true });
    }
    window.addEventListener("session-expired", onSessionExpired);
    return () => window.removeEventListener("session-expired", onSessionExpired);
  }, [navigate]);

  return null;
}

function App() {

  return (
    <DarkModeProvider>
      <LeaveGuardProvider>
        <Router>
          <SessionExpiredGuard />
          <Routes>
            <Route path="/" element={<Login/>}/>
            <Route element={<ProtectedShell />}>
              <Route path="/home" element={<Index/>}/>
              <Route path="/history" element={<History/>}/>
              <Route path="/questionselect" element={<Questionselect/>}/>
              <Route path="/questions" element={<Questions/>}/>
              <Route path="/controlpanel" element={<ControlPanelRoute><Control/></ControlPanelRoute>}/>
            </Route>
            <Route path="*" element={<Login/>}/>
          </Routes>
        </Router>
      </LeaveGuardProvider>
    </DarkModeProvider>
    
  )
}

export default App;
