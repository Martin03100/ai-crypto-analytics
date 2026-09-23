import { Menu } from "lucide-react";
import { useState } from "react";
import { Outlet } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";
import DailyDigest from "../components/DailyDigest";
import GlobalSearch from "../components/GlobalSearch";
import Sidebar from "../components/Sidebar";
import { useLanguage } from "../context/LanguageContext";

export default function Layout() {
  const { t } = useLanguage();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main className="main">
        <div className="header-row">
          <button className="mobile-menu-btn" onClick={() => setMenuOpen(true)} aria-label={t("common.openMenu")}>
            <Menu size={18} />
          </button>
          <GlobalSearch />
        </div>

        <DailyDigest />

        <Outlet />
      </main>

      <ChatWidget />
    </div>
  );
}
