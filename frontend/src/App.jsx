import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { useLanguage } from "./context/LanguageContext";
import Layout from "./pages/Layout";

// Route-based code splitting: kazda stranka je samostatny JS chunk, ktory
// sa stiahne az ked ju pouzivatel skutocne navstivi, namiesto toho, aby sa
// cela appka (vratane vsetkych grafov, chatu, exportu...) stiahla naraz pri
// prvom nacitani. Auth je vynimka - ostava eager (staticky) import, lebo je
// to prva stranka, ktoru takmer kazdy navstivi hned po nacitani appky, takze
// lazy-loading by tam len pridal zbytocny extra network round-trip.
import Auth from "./pages/Auth";
import { PrivacyPolicy, TermsOfService } from "./pages/Legal";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Forecast = lazy(() => import("./pages/Forecast"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const Market = lazy(() => import("./pages/Market"));
const Account = lazy(() => import("./pages/Account"));
const Settings = lazy(() => import("./pages/Settings"));

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
  if (checking) return <FullScreenLoader />;
  if (!user) return <Navigate to="/auth" replace />;
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
      <Suspense fallback={<FullScreenLoader />}>
        <Routes>
          <Route path="/auth" element={user ? <Navigate to="/dashboard" replace /> : <Auth />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfService />} />
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
      </Suspense>
    </>
  );
}
