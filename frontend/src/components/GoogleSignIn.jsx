/** "Continue with Google" (Google Identity Services). Hidden until the server has a Google client ID. */

import { useEffect, useRef } from "react";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";

const SCRIPT_URL = "https://accounts.google.com/gsi/client";
let scriptPromise;

function loadScript() {
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SCRIPT_URL;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => { scriptPromise = null; reject(new Error("google script")); };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

export default function GoogleSignIn({ onCredential }) {
  const { google_client_id: clientId } = useAppConfig();
  const { t, lang } = useLanguage();
  const ref = useRef(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;

  useEffect(() => {
    if (!clientId) return undefined;
    let cancelled = false;
    loadScript().then(() => {
      const gsi = window.google?.accounts?.id;
      if (cancelled || !ref.current || !gsi) return;
      gsi.initialize({ client_id: clientId, callback: (res) => callback.current(res.credential), ux_mode: "popup" });
      gsi.renderButton(ref.current, {
        theme: document.documentElement.dataset.theme === "dark" ? "filled_black" : "outline",
        size: "large", text: "continue_with", shape: "pill", width: Math.min(360, ref.current.offsetWidth || 320),
        locale: lang === "cs" ? "cs" : lang,
      });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [clientId, lang]);

  if (!clientId) return null;
  return (
    <div className="google-signin">
      <div className="google-signin-divider"><span>{t("auth.or")}</span></div>
      <div ref={ref} className="google-signin-button" data-testid="google-signin" />
    </div>
  );
}
