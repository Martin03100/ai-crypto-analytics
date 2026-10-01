/** App entry point. */

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./context/AuthContext";
import { ConfirmProvider } from "./context/ConfirmContext";
import { ProvidersProvider } from "./context/ProvidersContext";
import { ToastProvider } from "./context/ToastContext";
import { LanguageProvider } from "./context/LanguageContext";
import { ThemeProvider } from "./context/ThemeContext";
import { CurrencyProvider } from "./context/CurrencyContext";
import { startLabelAssociation } from "./utils/a11yLabels";
import { initMonitoring } from "./utils/monitoring";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "./styles/app.css";
import { initPwa } from "./pwa";

startLabelAssociation();
initMonitoring();
initPwa();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <LanguageProvider>
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
        </LanguageProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
