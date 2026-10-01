/** App layout. */

import { Menu, MoreHorizontal, RefreshCw, WifiOff } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";
import ErrorBoundary from "../components/ErrorBoundary";
import OnboardingTour from "../components/OnboardingTour";
import Sidebar, { BrandMark } from "../components/Sidebar";
import ShortcutsHelp from "../components/ShortcutsHelp";
import VerifyEmailGate from "../components/VerifyEmailGate";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useNavLinks } from "../hooks/useNavLinks";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { PWA_UPDATE_EVENT, updateApp } from "../pwa";

function ContentLoader() {
  const { t } = useLanguage();
  return (
    <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>
      {t("app.loading")}
    </div>
  );
}

function BottomNav({ onMore }) {
  const { t } = useLanguage();
  const { main } = useNavLinks();
  return (
    <nav className="bottom-nav" aria-label={t("nav.label")}>
      {main.map(({ to, short, icon: Icon }) => (
        <NavLink key={to} to={to} className={({ isActive }) => `bottom-nav-item ${isActive ? "active" : ""}`}>
          <Icon size={19} />
          <span>{short}</span>
        </NavLink>
      ))}
      <button type="button" className="bottom-nav-item" onClick={onMore}>
        <MoreHorizontal size={19} />
        <span>{t("nav.more")}</span>
      </button>
    </nav>
  );
}

function OfflineBanner() {
  const { t } = useLanguage();
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div className="offline-banner" role="status">
      <WifiOff size={15} /> {t("app.offline")}
    </div>
  );
}

function UpdatePrompt() {
  const { t } = useLanguage();
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const show = () => setVisible(true);
    window.addEventListener(PWA_UPDATE_EVENT, show);
    return () => window.removeEventListener(PWA_UPDATE_EVENT, show);
  }, []);
  if (!visible) return null;
  return (
    <div className="toast update-toast" role="status">
      <RefreshCw size={15} />
      <span style={{ flex: 1 }}>{t("pwa.updateReady")}</span>
      <button className="btn btn-primary btn-sm" onClick={updateApp}>{t("pwa.updateButton")}</button>
      <button className="btn btn-ghost btn-sm" onClick={() => setVisible(false)}>{t("common.later")}</button>
    </div>
  );
}

function PageTransition({ children }) {
  const { pathname } = useLocation();
  return (
    <div key={pathname} className="page-transition">
      <ErrorBoundary inline>{children}</ErrorBoundary>
    </div>
  );
}

export default function Layout() {
  const { t } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useAuth();
  const [showShortcuts, setShowShortcuts] = useState(false);
  const closeShortcuts = useCallback(() => setShowShortcuts(false), []);
  useKeyboardShortcuts(useCallback(() => setShowShortcuts(true), []));

  if (user?.emailVerified === false) return <VerifyEmailGate />;

  return (
    <div className="shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main className="main">
        <div className="mobile-topbar">
          <div className="brand"><BrandMark /><div className="brand-name">AI Crypto Analytics</div></div>
          <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t("common.openMenu")}>
            <Menu size={17} />
          </button>
        </div>
        <OfflineBanner />

        <Suspense fallback={<ContentLoader />}>
          <PageTransition>
            <Outlet />
          </PageTransition>
        </Suspense>
      </main>

      <BottomNav onMore={() => setMenuOpen(true)} />
      <UpdatePrompt />
      <ChatWidget />
      <OnboardingTour onNeedSidebar={setMenuOpen} />
      {showShortcuts && <ShortcutsHelp onClose={closeShortcuts} />}
    </div>
  );
}
