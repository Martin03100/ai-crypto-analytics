/** Error boundary. */

import { Component } from "react";
import { reportError } from "../utils/monitoring";

const FALLBACK_TEXT = {
  en: {
    title: "Something went wrong",
    body: "This part of the app hit an unexpected error. Reloading the page usually fixes it.",
    reload: "Reload page",
    retry: "Try again",
  },
  sk: {
    title: "Niečo sa pokazilo",
    body: "V tejto časti appky nastala neočakávaná chyba. Zvyčajne pomôže obnovenie stránky.",
    reload: "Obnoviť stránku",
    retry: "Skúsiť znova",
  },
  cs: {
    title: "Něco se pokazilo",
    body: "V této části aplikace nastala neočekávaná chyba. Obvykle pomůže obnovení stránky.",
    reload: "Obnovit stránku",
    retry: "Zkusit znovu",
  },
};

function readLang() {
  try {
    const stored = localStorage.getItem("aca_lang");
    return FALLBACK_TEXT[stored] ? stored : "en";
  } catch {
    return "en";
  }
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info);
    reportError(error, { extra: { componentStack: info?.componentStack } });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const t = FALLBACK_TEXT[readLang()];
    if (this.props.inline) {
      // Page-level fallback: keeps the sidebar and navigation usable.
      return (
        <div className="card" role="alert" style={{ textAlign: "center", padding: "36px 24px" }}>
          <h2 style={{ fontSize: 18, margin: "0 0 8px" }}>{t.title}</h2>
          <p className="text-sub" style={{ margin: "0 auto 16px", maxWidth: 420 }}>{t.body}</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-sm" onClick={() => this.setState({ hasError: false })}>{t.retry}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => window.location.reload()}>{t.reload}</button>
          </div>
        </div>
      );
    }
    return (
      <div
        style={{
          minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
          flexDirection: "column", gap: 14, padding: 24, textAlign: "center",
          background: "#030712", color: "#e6e8ee", fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ fontSize: 40 }}>⚠️</div>
        <h1 style={{ fontSize: 20, margin: 0 }}>{t.title}</h1>
        <p style={{ fontSize: 14, color: "#9aa1b2", maxWidth: 380, margin: 0 }}>{t.body}</p>
        <button
          onClick={() => window.location.reload()}
          style={{
            marginTop: 8, padding: "10px 20px", borderRadius: 8, border: "none",
            background: "#22d3ee", color: "#04141a", fontWeight: 600, fontSize: 14, cursor: "pointer",
          }}
        >
          {t.reload}
        </button>
      </div>
    );
  }
}
