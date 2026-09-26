import { useEffect, useRef } from "react";

/** Cloudflare Turnstile (bezplatna CAPTCHA). Zobrazi sa len ak je na Netlify
 * nastavene VITE_TURNSTILE_SITE_KEY - inak komponent nic nevykresli. Token je
 * jednorazovy: rodic po kazdom pouziti zmeni `key`, cim sa widget obnovi. */
const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
let scriptPromise;

function loadScript() {
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

export default function Turnstile({ onToken }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!SITE_KEY) return undefined;
    let widgetId;
    let cancelled = false;
    loadScript().then(() => {
      if (cancelled || !ref.current || !window.turnstile) return;
      widgetId = window.turnstile.render(ref.current, {
        sitekey: SITE_KEY, callback: onToken,
        "expired-callback": () => onToken(""), "error-callback": () => onToken(""),
      });
    }).catch(() => {});
    return () => {
      cancelled = true;
      if (widgetId !== undefined && window.turnstile) window.turnstile.remove(widgetId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!SITE_KEY) return null;
  return <div ref={ref} style={{ margin: "8px 0" }} />;
}
