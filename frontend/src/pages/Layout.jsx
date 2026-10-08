/** App layout. */

import { Menu, MoreHorizontal, RefreshCw, Search, WifiOff } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import AnnouncementBar from "../components/AnnouncementBar";
import ChatWidget from "../components/ChatWidget";
import CommandPalette from "../components/CommandPalette";
import { openPalette } from "../utils/viewHelpers";
import ErrorBoundary from "../components/ErrorBoundary";
import NotificationBell from "../components/NotificationBell";
import OnboardingTour from "../components/OnboardingTour";
import Sidebar, { BrandMark } from "../components/Sidebar";
import ShortcutsHelp from "../components/ShortcutsHelp";
import { SkeletonLines } from "../components/Skeleton";
import VerifyEmailGate from "../components/VerifyEmailGate";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useNavLinks } from "../hooks/useNavLinks";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { PWA_UPDATE_EVENT, updateApp } from "../pwa";

function ContentLoader() {
  const { t } = useLanguage();
  return (
    <div className="page-skeleton" role="status" aria-label={t("app.loading")}>
      <div className="skeleton" style={{ height: 28, width: "40%", marginBottom: 18 }} />
      <div className="card"><SkeletonLines count={3} /></div>
      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <div className="card"><SkeletonLines count={4} /></div>
        <div className="card"><SkeletonLines count={4} /></div>
      </div>
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
  const { chat_enabled } = useAppConfig();
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
          <div style={{ display: "flex", gap: 6 }}>
            <button className="mobile-menu-btn" onClick={openPalette} aria-label={t("palette.trigger")}>
              <Search size={17} />
            </button>
            <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t("common.openMenu")}>
              <Menu size={17} />
            </button>
          </div>
        </div>
        <OfflineBanner />
        <AnnouncementBar />

        <Suspense fallback={<ContentLoader />}>
          <PageTransition>
            <Outlet />
          </PageTransition>
        </Suspense>
      </main>

      <NotificationBell />
      <BottomNav onMore={() => setMenuOpen(true)} />
      <UpdatePrompt />
      {chat_enabled && <ChatWidget />}
      <OnboardingTour onNeedSidebar={setMenuOpen} />
      {showShortcuts && <ShortcutsHelp onClose={closeShortcuts} />}
      <CommandPalette />
    </div>
  );
}
