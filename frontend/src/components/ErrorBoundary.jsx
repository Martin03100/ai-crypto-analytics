import { Component } from "react";

/**
 * Error Boundary — bez neho by AKYKOLVEK neošetrený pád v React strome
 * (napr. neočakávaný tvar dát z API) spôsobil úplne bielu, prázdnu
 * stránku bez akéhokoľvek vysvetlenia. Toto zachytí taký pád a zobrazí
 * priateľský fallback namiesto toho.
 *
 * Zámerne NEPOUŽÍVA i18n systém (useLanguage/translate) — ak by problém
 * spôsobil práve tento systém, boundary by tým pádom sama spadla. Jazyk
 * preto číta priamo z localStorage (rovnaký kľúč ako LanguageContext) a
 * texty má vlastné, minimálne, aby fungovala nezávisle od zvyšku appky.
 */
const FALLBACK_TEXT = {
  en: {
    title: "Something went wrong",
    body: "This part of the app hit an unexpected error. Reloading the page usually fixes it.",
    reload: "Reload page",
  },
  sk: {
    title: "Niečo sa pokazilo",
    body: "V tejto časti appky nastala neočakávaná chyba. Zvyčajne pomôže obnovenie stránky.",
    reload: "Obnoviť stránku",
  },
  cs: {
    title: "Něco se pokazilo",
    body: "V této části aplikace nastala neočekávaná chyba. Obvykle pomůže obnovení stránky.",
    reload: "Obnovit stránku",
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
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const t = FALLBACK_TEXT[readLang()];
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
