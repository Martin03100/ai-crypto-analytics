/** App layout. */

import { Menu } from "lucide-react";
import { Suspense, useCallback, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";
import OnboardingTour from "../components/OnboardingTour";
import Sidebar from "../components/Sidebar";
import ShortcutsHelp from "../components/ShortcutsHelp";
import VerifyEmailGate from "../components/VerifyEmailGate";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";

function ContentLoader() {
  const { t } = useLanguage();
  return (
    <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>
      {t("app.loading")}
    </div>
  );
}

function PageTransition({ children }) {
  const { pathname } = useLocation();
  return <div key={pathname} className="page-transition">{children}</div>;
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
        <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t("common.openMenu")}>
          <Menu size={18} />
        </button>

        <Suspense fallback={<ContentLoader />}>
          <PageTransition>
            <Outlet />
          </PageTransition>
        </Suspense>
      </main>

      <ChatWidget />
      <OnboardingTour onNeedSidebar={setMenuOpen} />
      {showShortcuts && <ShortcutsHelp onClose={closeShortcuts} />}
    </div>
  );
}
