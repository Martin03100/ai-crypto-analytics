import { LayoutDashboard, LineChart, LogOut, Settings as SettingsIcon, Sparkles, TrendingUp, User, Wallet, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";

export default function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const initial = (user?.username || "?").charAt(0).toUpperCase();

  const LINKS = [
    { to: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { to: "/forecast", label: t("nav.forecast"), icon: Sparkles },
    { to: "/portfolio", label: t("nav.portfolio"), icon: Wallet },
    { to: "/market", label: t("nav.market"), icon: TrendingUp },
    { to: "/account", label: t("nav.account"), icon: User },
    { to: "/settings", label: t("nav.settings"), icon: SettingsIcon },
  ];

  return (
    <>
      {/* Stmavene pozadie za vysuvacim menu na mobile - klikom naň sa menu
         zatvori (bezny UX vzor "tap outside to dismiss"). Na desktope sa
         nikdy nezobrazi (sidebar tam je bezny stlpec, nie prekryvna vrstva). */}
      <button
        type="button"
        className={`sidebar-backdrop ${open ? "open" : ""}`}
        onClick={onClose}
        aria-label={t("common.closeMenu")}
        tabIndex={open ? 0 : -1}
      />
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><LineChart size={18} /></div>
          <div>
            <div className="brand-name">AI Crypto Analytics</div>
            <div className="brand-sub">2026 Edition</div>
          </div>
          {open && (
            <button className="mobile-menu-btn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label={t("common.closeMenu")}>
              <X size={18} />
            </button>
          )}
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              onClick={onClose}
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-avatar">{initial}</div>
            <div className="user-name">{user?.username}</div>
          </div>
          <button className="logout-btn" onClick={logout}>
            <LogOut size={14} /> {t("nav.logout")}
          </button>
        </div>
      </aside>
    </>
  );
}
