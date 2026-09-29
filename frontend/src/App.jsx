/** App routes. */

import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Landing from "./pages/Landing";
import { useAuth } from "./context/AuthContext";
import { useLanguage } from "./context/LanguageContext";
import Layout from "./pages/Layout";

import Auth from "./pages/Auth";
import { PrivacyPolicy, TermsOfService } from "./pages/Legal";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Forecast = lazy(() => import("./pages/Forecast"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const Market = lazy(() => import("./pages/Market"));
const Account = lazy(() => import("./pages/Account"));
const Settings = lazy(() => import("./pages/Settings"));
const SharedForecast = lazy(() => import("./pages/SharedForecast"));

function FullScreenLoader() {
  const { t } = useLanguage();
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--text-tertiary)", fontSize: 13 }}>
      {t("app.loading")}
    </div>
  );
}

function RequireAuth({ children }) {
  const { user, checking } = useAuth();
  const location = useLocation();
  if (checking) return <FullScreenLoader />;
  if (!user) return location.pathname === "/" ? <Landing /> : <Navigate to="/auth" replace />;
  return children;
}

export default function App() {
  const { user, checking } = useAuth();

  if (checking) return <FullScreenLoader />;

  return (
    <>
      <div className="grid-layer" aria-hidden="true" />
      <div className="aurora-layer" aria-hidden="true"><div className="aurora-blob-3" /></div>
      <div className="grain-layer" aria-hidden="true" />
      <Routes>
        <Route path="/auth" element={user ? <Navigate to="/forecast" replace /> : <Auth />} />
        <Route path="/privacy" element={<PrivacyPolicy />} />
        <Route path="/terms" element={<TermsOfService />} />
        <Route path="/share/:token" element={<Suspense fallback={<FullScreenLoader />}><SharedForecast /></Suspense>} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="forecast" element={<Forecast />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="market" element={<Market />} />
          <Route path="account" element={<Account />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
