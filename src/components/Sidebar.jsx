import React from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Calendar,
  Users,
  Phone,
  Settings,
  LogOut,
  CalendarPlus,
  X,
  BarChart3,
  Megaphone,
  FileCheck,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";

const Sidebar = ({ isOpen, setIsOpen }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { clinicName, role, hasPermission, logout, agencyBranding, language } = useAuth();

  const t = translations[language] || translations.en;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const allNavItems = [
    { name: t.dashboard,    path: "/",            icon: LayoutDashboard, permission: 'dashboard:read' },
    { name: t.analytics,    path: "/analytics",   icon: BarChart3,       permission: 'dashboard:read' },
    { name: t.appointments, path: "/appointments", icon: Calendar,         permission: 'appointments:read' },
    { name: t.patients,     path: "/patients",     icon: Users,            permission: 'patients:read' },
    { name: t.call_logs,    path: "/calls",        icon: Phone,            permission: 'calls:read' },
    { name: "Outbound AI",  path: "/outbound-campaigns", icon: Megaphone,  permission: 'calls:read' },
    { name: "Prior Auth",   path: "/prior-auth",   icon: FileCheck,        permission: 'dashboard:read' },
    { name: t.settings,     path: "/settings",     icon: Settings,         permission: 'settings:read' },
  ];

  // Sirf wahi nav items dikhao jo user ke role mein allowed hain
  const navItems = allNavItems.filter(item => hasPermission(item.permission));

  const displayName = clinicName || "Bytelytic OS";

  // Role ke liye human-readable label
  const roleLabels = { 
    owner: t.role_admin || 'Admin', 
    doctor: t.role_doctor || 'Doctor', 
    front_desk: t.role_front_desk || 'Front Desk', 
    read_only: t.role_read_only || 'Read Only' 
  };
  const roleLabel = roleLabels[role] || (t.role_admin || 'Admin');

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={`w-[210px] flex flex-col h-screen fixed left-0 top-0 z-50 transition-transform duration-300 ease-in-out sidebar-glass ${
          isOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full lg:translate-x-0"
        }`}
        style={{
          background: "linear-gradient(180deg, #1e4535 0%, #1a3a2e 58%, #122f23 100%)",
        }}
      >
        {/* Logo area */}
        <div className="px-5 pt-6 pb-5">
          <div className="flex items-center justify-between mb-1">
            {agencyBranding ? (
              <div className="flex items-center gap-2.5">
                {agencyBranding.logo_url ? (
                  <img
                    src={agencyBranding.logo_url}
                    alt={agencyBranding.name}
                    className="w-8 h-8 rounded-[0.5rem] object-contain flex-shrink-0 bg-white/10 p-0.5"
                  />
                ) : (
                  <div
                    className="w-8 h-8 rounded-[0.5rem] flex items-center justify-center flex-shrink-0 text-xs font-bold text-[#1a3a2e]"
                    style={{ backgroundColor: agencyBranding.brand_color_secondary || "#7FCD4D" }}
                  >
                    {agencyBranding.name ? agencyBranding.name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase() : "AG"}
                  </div>
                )}
                <div>
                  <p className="text-white font-extrabold text-sm leading-none tracking-tight uppercase max-w-[120px] truncate">
                    {agencyBranding.name || "Agency"}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                {/* Cross / medical icon */}
                <div
                  className="w-8 h-8 rounded-[0.5rem] flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: "#7FCD4D" }}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="5.5" y="1" width="3" height="12" rx="1.5" fill="#1a3a2e"/>
                    <rect x="1" y="5.5" width="12" height="3" rx="1.5" fill="#1a3a2e"/>
                  </svg>
                </div>
                <div>
                  <p className="text-white font-extrabold text-sm leading-none tracking-tight uppercase">
                    BYTELYTIC
                  </p>
                  <p className="text-white font-extrabold text-sm leading-none tracking-tight uppercase">
                    OS
                  </p>
                </div>
              </div>
            )}
            <button
              onClick={() => setIsOpen(false)}
              className="lg:hidden p-1 text-white/30 hover:text-white/60 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[0.65rem] font-semibold mt-2 flex items-center gap-1.5" style={{ color: "rgba(127,205,77,0.7)" }}>
            <span
              className="inline-block px-1.5 py-0.5 rounded text-[0.6rem] uppercase tracking-wider font-bold"
              style={{ backgroundColor: 'rgba(127,205,77,0.12)', color: 'rgba(127,205,77,0.85)' }}
            >
              {roleLabel}
            </span>
            {t.portal || "Portal"}
          </p>
        </div>

        {/* Subtle divider */}
        <div className="mx-5 h-px" style={{ backgroundColor: "rgba(255,255,255,0.06)" }} />

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5 overflow-y-auto hidden-scrollbar">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                onClick={() => setIsOpen(false)}
                className={`nav-item ${isActive ? "active" : ""}`}
              >
                <Icon className="w-[18px] h-[18px] flex-shrink-0" strokeWidth={isActive ? 2.5 : 2} />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Schedule appointment CTA */}
        <div className="px-3 pb-3">
          <button
            onClick={() => {
              navigate("/appointments?new=true");
              setIsOpen(false);
            }}
            className="w-full flex items-center justify-center gap-1.5 py-3 px-2 rounded-[0.625rem] font-bold text-[0.8rem] sm:text-sm transition-all hover:opacity-95 active:scale-[0.98] whitespace-nowrap"
            style={{ backgroundColor: "#7FCD4D", color: "#1a3a2e" }}
          >
            <CalendarPlus className="w-4 h-4 flex-shrink-0" />
            <span className="truncate">{t.schedule_appt || "Schedule Appointment"}</span>
          </button>
        </div>

        {/* Bottom separator */}
        <div className="mx-5 h-px mb-3" style={{ backgroundColor: "rgba(255,255,255,0.06)" }} />

        {/* Logout row */}
        <div className="px-3 pb-5">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 w-full rounded-[0.625rem] transition-all hover:bg-rose-500/10"
            style={{ color: "rgba(255,255,255,0.35)" }}
          >
            <LogOut className="w-4 h-4" />
            <span className="font-medium text-sm hover:text-rose-400 transition-colors">{t.sign_out || "Sign Out"}</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
