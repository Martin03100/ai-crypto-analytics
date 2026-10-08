/** Navigation entries shared by the sidebar and the mobile tab bar. */

import { BookOpen, CalendarDays, Crown, Gift, LayoutDashboard, Settings as SettingsIcon, ShieldCheck, Smartphone, Sparkles, Trophy, TrendingUp, User, Wallet } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { usePremium } from "./usePremium";

export function useNavLinks() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { mode } = usePremium();
  return {
    main: [
      { to: "/dashboard", label: t("nav.dashboard"), short: t("nav.dashboardShort"), icon: LayoutDashboard },
      { to: "/forecast", label: t("nav.forecast"), short: t("nav.forecastShort"), icon: Sparkles },
      { to: "/portfolio", label: t("nav.portfolio"), short: t("nav.portfolioShort"), icon: Wallet },
      { to: "/market", label: t("nav.market"), short: t("nav.marketShort"), icon: TrendingUp },
    ],
    extra: [
      { to: "/quick", label: t("nav.quick"), icon: Smartphone },
      { to: "/calendar", label: t("nav.calendar"), icon: CalendarDays },
      { to: "/track-record", label: t("nav.trackRecord"), icon: Trophy },
      { to: "/glossary", label: t("nav.glossary"), icon: BookOpen },
      { to: "/changelog", label: t("nav.changelog"), icon: Gift, badge: "changelog" },
    ],
    account: [
      { to: "/account", label: t("nav.account"), icon: User },
      { to: "/settings", label: t("nav.settings"), icon: SettingsIcon },
      ...(mode ? [{ to: "/premium", label: "Premium", icon: Crown }] : []),
      ...(user?.admin ? [{ to: "/admin", label: t("admin.title"), icon: ShieldCheck }] : []),
    ],
  };
}
