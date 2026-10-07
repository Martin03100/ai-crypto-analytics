/** Navigation entries shared by the sidebar and the mobile tab bar. */

import { Crown, LayoutDashboard, Settings as SettingsIcon, Sparkles, TrendingUp, User, Wallet } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";

export function useNavLinks() {
  const { t } = useLanguage();
  return {
    main: [
      { to: "/dashboard", label: t("nav.dashboard"), short: t("nav.dashboardShort"), icon: LayoutDashboard },
      { to: "/forecast", label: t("nav.forecast"), short: t("nav.forecastShort"), icon: Sparkles },
      { to: "/portfolio", label: t("nav.portfolio"), short: t("nav.portfolioShort"), icon: Wallet },
      { to: "/market", label: t("nav.market"), short: t("nav.marketShort"), icon: TrendingUp },
    ],
    account: [
      { to: "/account", label: t("nav.account"), icon: User },
      { to: "/settings", label: t("nav.settings"), icon: SettingsIcon },
      { to: "/premium", label: "Premium", icon: Crown },
    ],
  };
}
