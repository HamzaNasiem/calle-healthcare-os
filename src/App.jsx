import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Dashboard from './pages/Dashboard';
import Appointments from './pages/Appointments';
import Patients from './pages/Patients';
import CallLogs from './pages/CallLogs';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import OutboundCampaigns from './pages/OutboundCampaigns';
import PriorAuth from './pages/PriorAuth';

// ─── Public Route — logged-in user ko login/signup na dikhe ───────────────
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center animate-pulse"
          style={{ backgroundColor: '#7FCD4D' }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e" />
            <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e" />
          </svg>
        </div>
        <p className="text-xs text-on-surface-variant font-medium">Loading...</p>
      </div>
    </div>
  );
  if (isAuthenticated) return <Navigate to="/" replace />;
  return children;
};


// ─── Protected Route — bina login ke andar nahi aane deta ────────────────
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center animate-pulse"
          style={{ backgroundColor: '#7FCD4D' }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e" />
            <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e" />
          </svg>
        </div>
        <p className="text-xs text-on-surface-variant font-medium">Loading...</p>
      </div>
    </div>
  );
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

// ─── Require Auth Or Landing ───────────────────────────────────────────────
const RequireAuthOrLanding = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-3">
        <div
          className="w-9 h-9 rounded-[0.5rem] flex items-center justify-center animate-pulse"
          style={{ backgroundColor: '#7FCD4D' }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e" />
            <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e" />
          </svg>
        </div>
        <p className="text-xs text-on-surface-variant font-medium">Loading...</p>
      </div>
    </div>
  );

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// ─── Inner App — Router ke andar (useAuth use karne ke liye) ─────────────
function AppRoutes() {
  // Continuous keep-alive heartbeat (pings Render backend every 4 minutes while app is open)
  React.useEffect(() => {
    const pingBackend = () => {
      fetch("https://calle-healthcare-os.onrender.com/health", { method: "GET", mode: "no-cors" }).catch(() => {});
    };
    pingBackend();
    const interval = setInterval(pingBackend, 4 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Routes>
      {/* Public routes — sirf logged-OUT users ke liye */}
      <Route path="/login"           element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/forgot-password" element={<PublicRoute><ForgotPassword /></PublicRoute>} />
      {/* Reset password — token URL mein hota hai, auth check skip */}
      <Route path="/reset-password"  element={<ResetPassword />} />

      {/* Protected routes — sirf logged-IN users ke liye */}
      <Route
        path="/"
        element={
          <RequireAuthOrLanding>
            <Layout />
          </RequireAuthOrLanding>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="analytics"    element={<Analytics />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="patients"     element={<Patients />} />
        <Route path="calls"        element={<CallLogs />} />
        <Route path="outbound-campaigns" element={<OutboundCampaigns />} />
        <Route path="prior-auth"   element={<PriorAuth />} />
        <Route path="settings"     element={<Settings />} />
        <Route path="setup"        element={<Navigate to="/settings" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// ─── Error Boundary Component (Prevents Blank Screens) ────────────────────
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[React ErrorBoundary caught error]:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-surface p-6">
          <div className="card p-8 max-w-md w-full text-center space-y-4 shadow-xl border border-surface-container-high bg-white rounded-2xl">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-700 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-on-surface">Application Session Refresh Required</h2>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              Your browser session cache has updated. Click below to clear cache and reload.
            </p>
            {this.state.error && (
              <div className="p-3 bg-red-50 text-red-700 text-xs text-left rounded-lg font-mono overflow-auto max-h-32 border border-red-200">
                {String(this.state.error.message || this.state.error)}
              </div>
            )}
            <button
              onClick={() => {
                localStorage.clear();
                sessionStorage.clear();
                window.location.href = '/login';
              }}
              className="btn-primary w-full justify-center bg-[#396a00] text-white py-2.5 rounded-xl font-bold hover:opacity-90 transition-all cursor-pointer"
            >
              Reset Session & Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Root App — AuthProvider + BrowserRouter wrap ────────────────────────
function App() {
  return (
    <div className="w-screen min-h-screen overflow-x-hidden bg-surface">
      <BrowserRouter>
        <AuthProvider>
          <WebSocketProvider>
            <ErrorBoundary>
              <AppRoutes />
            </ErrorBoundary>
          </WebSocketProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;

