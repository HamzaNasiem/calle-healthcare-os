import React, { useState, useRef, useEffect } from "react";
import { Bell, HelpCircle, Menu, Search, LogOut, Settings, User, Calendar, Phone, MessageSquare, AlertCircle, Info, Check } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { createClient } from "@supabase/supabase-js";
import { playNotificationChime, showBrowserNotification } from "../lib/notifications";

const Header = ({ onMenuClick, pageTitle = "Bytelytic OS" }) => {
  const { clinicId, clinicName, user, role, logout, language, setLanguage } = useAuth();
  const displayName = clinicName || "Clinic";
  const initials = displayName
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const roleLabels = { owner: 'Admin', doctor: 'Doctor', front_desk: 'Front Desk', read_only: 'Read Only' };
  const roleLabel = roleLabels[role] || 'Admin';

  const [activeDropdown, setActiveDropdown] = useState(null);
  const dropdownRef = useRef(null);
  const [billingInfo, setBillingInfo] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (import.meta.env.VITE_DEDICATED_CLINIC_MODE === 'true') return;
    const token = localStorage.getItem("sb-token") || sessionStorage.getItem("sb-token");
    if (token) {
      api.get("/billing/usage")
        .then(res => { setBillingInfo(res.data.data); })
        .catch(() => { /* Silent fail — billing is non-critical */ });
    }
  }, []);

  // Fetch initial notifications
  const fetchNotifications = async () => {
    try {
      const res = await api.get("/notifications");
      setNotifications(res.data.data || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (error) {
      console.error("Failed to fetch notifications", error);
    }
  };

  // Setup real-time notifications subscription
  useEffect(() => {
    if (!clinicId) return;

    fetchNotifications();

    let subscription = null;

    const initRealtime = async () => {
      let url = localStorage.getItem('supabaseUrl');
      let anonKey = localStorage.getItem('supabaseAnonKey');

      if (!url || !anonKey) {
        try {
          const res = await api.get('/auth/config');
          url = res.data.supabaseUrl;
          anonKey = res.data.supabaseAnonKey;
          localStorage.setItem('supabaseUrl', url);
          localStorage.setItem('supabaseAnonKey', anonKey);
        } catch (e) {
          console.error("Failed to load supabase config for realtime", e);
          return;
        }
      }

      if (!url || !anonKey) return;

      try {
        const supabase = createClient(url, anonKey);
        
        subscription = supabase
          .channel('notifications-realtime')
          .on(
            'postgres_changes',
            {
              event: 'INSERT',
              schema: 'public',
              table: 'notifications',
              filter: `clinic_id=eq.${clinicId}`
            },
            (payload) => {
              const newNotif = payload.new;
              setNotifications(prev => [newNotif, ...prev.slice(0, 19)]);
              setUnreadCount(prev => prev + 1);

              // Trigger audible chime
              try {
                playNotificationChime();
              } catch (soundErr) {
                console.warn("Realtime audio alert error:", soundErr);
              }

              // Trigger desktop browser push notification
              try {
                showBrowserNotification(newNotif.title || "Bytelytic OS Notification", {
                  body: newNotif.body || "New notification received.",
                });
              } catch (pushErr) {
                console.warn("Realtime push alert error:", pushErr);
              }
            }
          )
          .subscribe();
      } catch (e) {
        console.error("Failed to initialize realtime subscription", e);
      }
    };

    initRealtime();

    return () => {
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, [clinicId]);

  const handleMarkAllRead = async () => {
    try {
      await api.post("/notifications/read-all");
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (e) {
      console.error("Failed to mark all as read", e);
    }
  };

  const handleMarkOneRead = async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (e) {
      console.error("Failed to mark notification read", e);
    }
  };

  const getNotificationIcon = (type) => {
    if (type.startsWith("appointment")) return Calendar;
    if (type.startsWith("call")) return Phone;
    if (type.startsWith("sms")) return MessageSquare;
    if (type.startsWith("system.error") || type.startsWith("noshow")) return AlertCircle;
    return Info;
  };

  const getIconBgColor = (type, isRead) => {
    if (!isRead) {
      if (type.startsWith("appointment")) return "bg-[#e8f5e9]";
      if (type.startsWith("call")) return "bg-[#e3f2fd]";
      if (type.startsWith("sms")) return "bg-[#e1f5fe]";
      if (type.startsWith("system.error") || type.startsWith("noshow")) return "bg-[#ffebee]";
      return "bg-[#f5f5f5]";
    }
    return "bg-surface-container-low";
  };

  const getIconColor = (type, isRead) => {
    if (!isRead) {
      if (type.startsWith("appointment")) return "text-[#2e7d32]";
      if (type.startsWith("call")) return "text-[#1565c0]";
      if (type.startsWith("sms")) return "text-[#0288d1]";
      if (type.startsWith("system.error") || type.startsWith("noshow")) return "text-[#c62828]";
      return "text-[#616161]";
    }
    return "text-on-surface-variant/40";
  };

  const formatTimeAgo = (dateStr) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return language === 'es' ? "Hace un momento" : "Just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return language === 'es' ? `Hace ${minutes}m` : `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return language === 'es' ? `Hace ${hours}h` : `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return language === 'es' ? `Hace ${days}d` : `${days}d ago`;
  };

  const toggleDropdown = (name) => {
    setActiveDropdown((prev) => (prev === name ? null : name));
  };

  return (
    <header
      className="h-14 bg-surface-container-lowest flex items-center justify-between px-6 sticky top-0 z-20"
      style={{ boxShadow: "0px 1px 0px rgba(24,28,28,0.06)" }}
    >
      {/* Left: hamburger (mobile) + search */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="p-2 -ml-1 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg lg:hidden transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Search bar – hidden on small screens, shown from md */}
        <div className="relative hidden md:block">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
          <input
            type="text"
            placeholder={language === 'es' ? "Buscar..." : "Search..."}
            className="w-60 pl-8 pr-4 py-2 text-sm outline-none text-on-surface placeholder-on-surface-variant/40 rounded-[0.625rem] transition-all duration-200"
            style={{
              backgroundColor: "#edf1ef",
              border: "none",
            }}
            onFocus={(e) => (e.target.style.backgroundColor = "#e5ebe8")}
            onBlur={(e) => (e.target.style.backgroundColor = "#edf1ef")}
          />
        </div>
      </div>

      {/* Center: page title (hidden on small screens) */}
      <span className="hidden lg:block absolute left-1/2 -translate-x-1/2 text-sm font-semibold text-on-surface-variant">
        {pageTitle}
      </span>

      {/* Right: notification, help, avatar */}
      <div className="flex items-center gap-2 relative" ref={dropdownRef}>
        
        {/* Trial Banner — shows when on trial (free or Stripe trialing) */}
        {import.meta.env.VITE_DEDICATED_CLINIC_MODE !== 'true' && billingInfo && (billingInfo.plan === "trial" || billingInfo.status === "trialing") && (
          <div className="hidden lg:flex items-center gap-2 bg-[#f4fbf7] border border-[#d6ede0] px-3 py-1 rounded-full text-xs text-[#204028] font-medium mr-2">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#7dbd42" }} />
            <span>Trial: <strong className="text-black">{Math.max(0, Math.ceil((new Date(billingInfo.trial_ends_at || billingInfo.billing_cycle_end) - new Date()) / (1000 * 60 * 60 * 24)))} days remaining</strong> → </span>
            <a href="/settings?tab=billing" className="text-[#396a00] hover:text-[#5ea334] font-bold transition-colors">Upgrade</a>
          </div>
        )}
        
        {/* Notifications */}
        <div>
          <button onClick={() => toggleDropdown('notifications')} className="relative p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors">
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full text-[0.65rem] font-bold text-white bg-red-600 flex items-center justify-center border border-white">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
          {activeDropdown === 'notifications' && (
            <div className="absolute top-full right-0 mt-1 w-80 bg-white rounded-xl shadow-lg border border-surface-container z-50 overflow-hidden">
              <div className="p-3 border-b border-surface-container flex justify-between items-center bg-surface-container-lowest">
                <span className="font-bold text-sm text-on-surface">{language === 'es' ? "Notificaciones" : "Notifications"}</span>
                {unreadCount > 0 && (
                  <button 
                    onClick={handleMarkAllRead} 
                    className="text-xs text-[#396a00] hover:text-[#5ea334] font-bold flex items-center gap-1 transition-colors"
                  >
                    <Check className="w-3.5 h-3.5" /> {language === 'es' ? "Marcar todo como leído" : "Mark all read"}
                  </button>
                )}
              </div>
              <div className="max-h-96 overflow-y-auto divide-y divide-surface-container-low">
                {notifications.length === 0 ? (
                  <div className="p-6 text-center text-on-surface-variant text-sm">
                    <Bell className="w-8 h-8 mx-auto mb-2 opacity-30 text-on-surface-variant" />
                    <p className="font-medium">{language === 'es' ? "¡Todo al día!" : "All caught up!"}</p>
                    <p className="text-xs opacity-60 mt-0.5 font-normal">
                      {language === 'es' ? "No hay nuevas notificaciones que mostrar" : "No new notifications to display"}
                    </p>
                  </div>
                ) : (
                  notifications.map((n) => {
                    const NotifIcon = getNotificationIcon(n.type);
                    return (
                      <div 
                        key={n.id} 
                        onClick={() => handleMarkOneRead(n.id)}
                        className={`p-3 flex gap-3 cursor-pointer hover:bg-surface-container-low transition-colors relative ${!n.is_read ? 'bg-[#f4fbf7]' : ''}`}
                      >
                        {/* Status Unread Dot Indicator */}
                        {!n.is_read && (
                          <span className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-[#7dbd42]" />
                        )}
                        
                        {/* Icon */}
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${getIconBgColor(n.type, n.is_read)}`}>
                          <NotifIcon className={`w-4 h-4 ${getIconColor(n.type, n.is_read)}`} />
                        </div>
                        
                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs text-on-surface leading-tight truncate ${!n.is_read ? 'font-bold' : 'font-medium'}`}>
                            {n.title}
                          </p>
                          <p className="text-[0.7rem] text-on-surface-variant leading-snug mt-0.5 break-words font-normal">
                            {n.body}
                          </p>
                          <span className="text-[0.65rem] text-on-surface-variant/60 block mt-1 font-medium">
                            {formatTimeAgo(n.created_at)}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Language Switcher */}
        <button
          onClick={() => setLanguage(language === "en" ? "es" : "en")}
          className="mr-1 px-2.5 py-1 text-xs font-bold rounded-lg border border-surface-container hover:bg-surface-container-low text-on-surface-variant hover:text-on-surface transition-all flex items-center gap-1.5 active:scale-95"
          title="Switch language / Cambiar idioma"
        >
          <span className={language === 'en' ? 'text-[#396a00]' : 'opacity-50'}>EN</span>
          <span className="opacity-30">|</span>
          <span className={language === 'es' ? 'text-[#396a00]' : 'opacity-50'}>ES</span>
        </button>

        {/* Help */}
        <div>
          <button onClick={() => toggleDropdown('help')} className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors">
            <HelpCircle className="w-5 h-5" />
          </button>
          {activeDropdown === 'help' && (
            <div className="absolute top-full right-0 mt-1 w-56 bg-white rounded-xl shadow-lg border border-surface-container z-50 overflow-hidden py-1">
              <a href="#" className="block px-4 py-2 hover:bg-surface-container text-sm text-on-surface">
                {language === 'es' ? "Documentación" : "Documentation"}
              </a>
              <a href="#" className="block px-4 py-2 hover:bg-surface-container text-sm text-on-surface">
                {language === 'es' ? "Videotutoriales" : "Video Tutorials"}
              </a>
              <a href="#" className="block px-4 py-2 hover:bg-surface-container text-sm text-on-surface">
                {language === 'es' ? "Contactar Soporte" : "Contact Support"}
              </a>
            </div>
          )}
        </div>

        {/* Avatar / Profile */}
        <div>
          <div
            onClick={() => toggleDropdown('profile')}
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ml-1 cursor-pointer flex-shrink-0 ring-2 ring-surface-container-low"
            style={{ backgroundColor: "#396a00" }}
          >
            {initials}
          </div>
          {activeDropdown === 'profile' && (
            <div className="absolute top-full right-0 mt-1 w-56 bg-white rounded-xl shadow-lg border border-surface-container z-50 overflow-hidden py-1">
              <div className="px-4 py-3 border-b border-surface-container mb-1 bg-surface-container-lowest">
                <p className="text-sm font-bold text-on-surface truncate">{displayName}</p>
                <p className="text-xs text-on-surface-variant truncate">{user?.email || '—'}</p>
                <span
                  className="inline-block mt-1 px-1.5 py-0.5 rounded text-[0.6rem] uppercase tracking-wider font-bold"
                  style={{ backgroundColor: 'rgba(57,106,0,0.1)', color: '#396a00' }}
                >
                  {roleLabel}
                </span>
              </div>
              <a href="/setup" className="flex items-center gap-2 px-4 py-2 hover:bg-surface-container text-sm text-on-surface">
                <Settings className="w-4 h-4" /> {language === 'es' ? "Configuración de Cuenta" : "Account Settings"}
              </a>
              <button 
                onClick={() => {
                  logout();
                  window.location.href = '/login';
                }}
                className="w-full flex items-center gap-2 px-4 py-2 hover:bg-surface-container text-sm text-rose-600"
              >
                <LogOut className="w-4 h-4" /> {language === 'es' ? "Cerrar Sesión" : "Sign Out"}
              </button>
            </div>
          )}
        </div>

      </div>
    </header>
  );
};

export default Header;
