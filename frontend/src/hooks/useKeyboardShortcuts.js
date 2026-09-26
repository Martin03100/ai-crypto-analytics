import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export const SHORTCUT_ROUTES = { d: "/dashboard", f: "/forecast", p: "/portfolio", m: "/market", a: "/account", s: "/settings" };

/** Klavesove skratky pre rychlu navigaciu. Ignoruju sa pri pisani do
 * formularov a pri kombinaciach s Ctrl/Cmd/Alt (tie patria prehliadacu). */
export function useKeyboardShortcuts(onHelp) {
  const navigate = useNavigate();
  useEffect(() => {
    function onKey(e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      if (e.key === "?") {
        e.preventDefault();
        onHelp();
        return;
      }
      const route = SHORTCUT_ROUTES[(e.key || "").toLowerCase()];
      if (route) {
        e.preventDefault();
        navigate(route);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navigate, onHelp]);
}
