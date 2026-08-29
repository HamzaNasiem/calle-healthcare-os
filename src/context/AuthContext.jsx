import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { clearAuth, getToken, getClinicInfo } from '../lib/api';
import api from '../lib/api';

// ─────────────────────────────────────────────────────────────────────────────
// Context Definition
// ─────────────────────────────────────────────────────────────────────────────
const AuthContext = createContext(null);

// Permission matrix — role ke hisaab se kya allow hai
const PERMISSIONS = {
  owner: [
    'dashboard:read',
    'appointments:read', 'appointments:write', 'appointments:delete',
    'patients:read', 'patients:write', 'patients:delete',
    'calls:read',
    'settings:read', 'settings:write',
    'staff:read', 'staff:write',
    'billing:read',
    'reports:read', 'reports:export',
  ],
  doctor: [
    'dashboard:read',
    'appointments:read', 'appointments:write',
    'patients:read', 'patients:write',
  ],
  front_desk: [
    'dashboard:read',
    'appointments:read', 'appointments:write', 'appointments:delete',
    'patients:read', 'patients:write',
    'calls:read',
  ],
  read_only: [
    'dashboard:read',
    'appointments:read',
    'patients:read',
  ],
};

// ─────────────────────────────────────────────────────────────────────────────
// AuthProvider
// ─────────────────────────────────────────────────────────────────────────────
export const AuthProvider = ({ children }) => {
  const [user, setUser]           = useState(null);
  const [role, setRole]           = useState(null);
  const [clinicId, setClinicId]   = useState(null);
  const [clinicName, setClinicName] = useState(null);
  const [timezone, setTimezone]   = useState('America/Chicago');
  const [language, setLanguageState] = useState(localStorage.getItem('lang') || 'en');
  const [loading, setLoading] = useState(true);
  const [agencyBranding, setAgencyBranding] = useState(null);

  // isAuthenticated — reactive (token check on every render)
  const isAuthenticated = !!getToken();

  // In-memory cache for Stale-While-Revalidate (SWR) fetching pattern
  const cacheRef = useRef({});

  const getCacheItem = useCallback((key) => {
    return cacheRef.current[key] || null;
  }, []);

  const setCacheItem = useCallback((key, value) => {
    cacheRef.current[key] = value;
  }, []);

  const setLanguage = useCallback((lang) => {
    localStorage.setItem('lang', lang);
    setLanguageState(lang);
  }, []);

  // ── Logout (defined before useEffect so it can be referenced) ──
  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setRole(null);
    setClinicId(null);
    setClinicName(null);
    setTimezone('America/Chicago');
    cacheRef.current = {}; // Clear in-memory cache on logout to avoid memory leaks / data pollution
    setLoading(false);
  }, []);


  // ── Bootstrap: storage se session restore karo ──
  useEffect(() => {
    const hostname = window.location.hostname;
    api.get(`/agencies/resolve-branding?domain=${hostname}`)
      .then((res) => {
        if (res.data && res.data.data) {
          const brand = res.data.data;
          setAgencyBranding(brand);
          if (brand.brand_color_primary) {
            document.documentElement.style.setProperty('--color-primary', brand.brand_color_primary);
          }
          if (brand.brand_color_secondary) {
            document.documentElement.style.setProperty('--color-secondary', brand.brand_color_secondary);
          }
        }
      })
      .catch(() => { /* Revert to default Bytelytic branding */ });

    const token = getToken();
    let info = getClinicInfo();

    // Safety net: loading ko hamesha 3 seconds mein false karo — blank screen prevent karo
    const safetyTimer = setTimeout(() => setLoading(false), 3000);

    if (!token) {
      clearTimeout(safetyTimer);
      setLoading(false);
      return;
    }

    if (info) {
      setClinicId(info.clinicId || "d3b07384-d113-46a6-a719-38cf89235d54");
      setClinicName(info.clinicName || "Sunrise Medical Clinic");
      setTimezone(info.timezone || 'America/Chicago');
      setRole(info.role || 'owner');
      setUser({ email: info.userEmail || "admin@sunriseclinic.com", id: info.userId || "demo-user-001" });
      // Agar cached info hai, loading turant false karo — flicker nahi hogi
      clearTimeout(safetyTimer);
      setLoading(false);
    }

    // Background mein token verify karo (UI block nahi hogi)
    api.get('/auth/me')
      .then((res) => {
        if (res.data) {
          const { role: r, email, userId, clinicId: cId, clinicName: cName, timezone: tz } = res.data;
          setUser({ email, id: userId });
          setRole(r || 'owner');
          if (cId) setClinicId(cId);
          if (cName) setClinicName(cName);
          if (tz) setTimezone(tz);
          const storage = localStorage.getItem('sb-token') ? localStorage : sessionStorage;
          storage.setItem('clinic-info', JSON.stringify({
            clinicId: cId || info?.clinicId,
            clinicName: cName || info?.clinicName,
            timezone: tz || info?.timezone,
            role: r || info?.role || 'owner',
            userEmail: email || info?.userEmail,
            userId: userId || info?.userId,
          }));
        }
      })
      .catch(() => {
        // Token invalid — wipe karo aur login pe bhejo
        clearAuth();
        setUser(null);
        setRole(null);
        setClinicId(null);
        setClinicName(null);
      })
      .finally(() => {
        clearTimeout(safetyTimer);
        setLoading(false);
      });
  }, []);


  // ── Idle Session Timeout (Configurable HIPAA Standard, default 15 minutes) ──
  useEffect(() => {
    if (!isAuthenticated) return;

    let timeoutId;
    
    const getIdleLimitMs = () => {
      const savedMins = parseInt(localStorage.getItem('bytelytic_idle_timeout_mins') || '15', 10);
      const validMins = (!isNaN(savedMins) && savedMins >= 1 && savedMins <= 1440) ? savedMins : 15;
      return validMins * 60 * 1000;
    };

    let idleLimit = getIdleLimitMs();

    const resetTimer = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        console.log(`[AuthContext] User idle session timeout reached (${idleLimit / 60000} mins). Invaliding session.`);
        logout();
        window.location.href = '/login';
      }, idleLimit);
    };

    const handleTimeoutUpdated = () => {
      idleLimit = getIdleLimitMs();
      resetTimer();
    };

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    events.forEach(event => window.addEventListener(event, resetTimer));
    window.addEventListener('bytelytic_idle_timeout_changed', handleTimeoutUpdated);
    window.addEventListener('storage', handleTimeoutUpdated);

    resetTimer();

    return () => {
      clearTimeout(timeoutId);
      events.forEach(event => window.removeEventListener(event, resetTimer));
      window.removeEventListener('bytelytic_idle_timeout_changed', handleTimeoutUpdated);
      window.removeEventListener('storage', handleTimeoutUpdated);
    };
  }, [isAuthenticated, logout]);

  // ── Login — Login.jsx aur Signup.jsx is ko call karte hain ──
  const login = useCallback(({
    token, refreshToken, clinicId: cId, clinicName: cName,
    timezone: tz, role: r, email, userId, rememberMe = true,
  }) => {
    const storage      = rememberMe ? localStorage : sessionStorage;
    const otherStorage = rememberMe ? sessionStorage : localStorage;

    storage.setItem('sb-token', token);
    if (refreshToken) storage.setItem('sb-refresh-token', refreshToken);
    storage.setItem('clinic-info', JSON.stringify({
      clinicId: cId, clinicName: cName, timezone: tz,
      role: r || 'owner', userEmail: email, userId,
    }));

    // Dusri storage clean karo (conflicts avoid)
    ['sb-token', 'sb-refresh-token', 'clinic-info'].forEach(k => otherStorage.removeItem(k));

    setUser({ email, id: userId });
    setRole(r || 'owner');
    setClinicId(cId);
    setClinicName(cName);
    setTimezone(tz);
  }, []);

  // ── hasPermission ──
  const hasPermission = useCallback((permission) => {
    if (!role) return false;
    return (PERMISSIONS[role] || []).includes(permission);
  }, [role]);

  // ── isRole ──
  const isRole = useCallback((...roles) => roles.includes(role), [role]);

  const value = {
    user, role, clinicId, clinicName, timezone,
    loading, isAuthenticated,
    login, logout,
    hasPermission, isRole,
    language, setLanguage,
    agencyBranding,
    getCacheItem,
    setCacheItem,
    ROLES: { OWNER: 'owner', DOCTOR: 'doctor', FRONT_DESK: 'front_desk', READ_ONLY: 'read_only' },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// ─────────────────────────────────────────────────────────────────────────────
// useAuth hook
// ─────────────────────────────────────────────────────────────────────────────
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
};
