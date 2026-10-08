/** Navigation sidebar (desktop) and slide-in sheet (mobile "More"). */

import { LineChart, LogOut, Search, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useNavLinks } from "../hooks/useNavLinks";
import { hasUnreadChangelog } from "../data/changelog";
import { openPalette } from "../utils/viewHelpers";
import FeedbackButton from "./FeedbackButton";

export function BrandMark({ size = 16 }) {
  return <div className="brand-mark" aria-hidden="true"><LineChart size={size} strokeWidth={2.25} /></div>;
}

export default function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const links = useNavLinks();
  const initial = (user?.username || "?").charAt(0).toUpperCase();

  const renderLink = ({ to, label, icon: Icon, badge }) => (
    <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} onClick={onClose}>
      <Icon size={16} />
      {label}
      {badge === "changelog" && hasUnreadChangelog() && <span className="nav-new" aria-label={t("changelog.newBadge")}>{t("changelog.newBadge")}</span>}
    </NavLink>
  );

  return (
    <>
      <button
        type="button"
        className={`sidebar-backdrop ${open ? "open" : ""}`}
        onClick={onClose}
        aria-label={t("common.closeMenu")}
        tabIndex={open ? 0 : -1}
      />
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label={t("nav.label")}>
        <div className="brand">
          <BrandMark />
          <div className="brand-name">AI Crypto Analytics</div>
          {open && (
            <button className="mobile-menu-btn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label={t("common.closeMenu")}>
              <X size={16} />
            </button>
          )}
        </div>

        <button type="button" className="palette-trigger" onClick={() => { onClose?.(); openPalette(); }} aria-keyshortcuts="Control+K">
          <Search size={14} aria-hidden="true" /> <span>{t("palette.trigger")}</span> <kbd>Ctrl K</kbd>
        </button>

        <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {links.main.map(renderLink)}
          <div className="nav-section">{t("nav.sectionExplore")}</div>
          {links.extra.map(renderLink)}
          <div className="nav-section">{t("nav.sectionAccount")}</div>
          {links.account.map(renderLink)}
        </nav>

        <FeedbackButton className="sidebar-feedback" />

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-avatar" aria-hidden="true">{initial}</div>
            <div className="user-name">{user?.username}</div>
          </div>
          <button className="logout-btn" onClick={logout} aria-label={t("nav.logout")} title={t("nav.logout")}>
            <LogOut size={15} />
          </button>
        </div>
      </aside>
    </>
  );
}
