import { Menu } from "lucide-react";
import { Suspense, useState } from "react";
import { Outlet } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";
import DailyDigest from "../components/DailyDigest";
import OnboardingTour from "../components/OnboardingTour";
import Sidebar from "../components/Sidebar";
import { useLanguage } from "../context/LanguageContext";

/** Ľahký loading stav LEN pre obsahovú časť (nie cez celú obrazovku) - kým sa
 * stiahne JS balíček pre danú stránku (lazy-loaded route, viď App.jsx).
 * Sidebar aj hlavička ostávajú na mieste, nezmiznú počas prepínania stránok. */
function ContentLoader() {
  const { t } = useLanguage();
  return (
    <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: 13 }}>
      {t("app.loading")}
    </div>
  );
}

export default function Layout() {
  const { t } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main className="main">
        <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t("common.openMenu")}>
          <Menu size={18} />
        </button>

        <DailyDigest />

        <Suspense fallback={<ContentLoader />}>
          <Outlet />
        </Suspense>
      </main>

      <ChatWidget />
      <OnboardingTour onNeedSidebar={setMenuOpen} />
    </div>
  );
}
