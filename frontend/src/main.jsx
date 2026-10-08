/** App entry point. */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AppConfigProvider } from "./context/AppConfigContext";
import { AuthProvider } from "./context/AuthContext";
import { ConfirmProvider } from "./context/ConfirmContext";
import { ProvidersProvider } from "./context/ProvidersContext";
import { ToastProvider } from "./context/ToastContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ThemeProvider } from "./context/ThemeContext";
import { CurrencyProvider } from "./context/CurrencyContext";
import { startLabelAssociation } from "./utils/a11yLabels";
import { initMonitoring } from "./utils/monitoring";
import { initAnalytics, rememberUtmSource } from "./utils/analytics";
import { captureReferralCode } from "./utils/referral";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "./styles/app.css";
import "./styles/extras.css";
import { initPwa } from "./pwa";
import { initialLang } from "./context/LanguageContext";
import { loadLanguage } from "./i18n/translations";

startLabelAssociation();
initMonitoring();
initPwa();
rememberUtmSource();
captureReferralCode();
initAnalytics();

// The saved language is loaded before the first paint, so the app never flashes in English.
loadLanguage(initialLang()).finally(() => ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <LanguageProvider>
          <AppConfigProvider>
            <ThemeProvider>
              <CurrencyProvider>
                <AuthProvider>
                  <ProvidersProvider>
                    <ToastProvider>
                      <ConfirmProvider>
                        <App />
                      </ConfirmProvider>
                    </ToastProvider>
                  </ProvidersProvider>
                </AuthProvider>
              </CurrencyProvider>
            </ThemeProvider>
          </AppConfigProvider>
        </LanguageProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
));
