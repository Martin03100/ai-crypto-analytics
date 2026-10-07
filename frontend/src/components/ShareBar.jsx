/** Share the current page on social networks. */

import { Link2, Share2 } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { trackEvent } from "../utils/analytics";
import { copyToClipboard } from "../utils/copyToClipboard";
import { shareTargets } from "../utils/share";

export default function ShareBar({ text, url = window.location.href.split("#")[0] }) {
  const { t } = useLanguage();
  const { push } = useToast();
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  const copy = async () => {
    const ok = await copyToClipboard(url);
    push(t(ok ? "common.copied" : "common.copyFailed"), ok ? "success" : "error", { translated: true });
    if (ok) trackEvent("share", { target: "copy" });
  };
  const nativeShare = () => navigator.share({ title: "AI Crypto Analytics", text, url }).catch(() => {});

  return (
    <div className="share-bar" aria-label={t("shareBar.label")}>
      <span className="text-sub share-bar-label">{t("shareBar.label")}</span>
      {canShare && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={nativeShare}><Share2 size={13} /> {t("shareBar.share")}</button>
      )}
      {shareTargets(url, text).map((s) => (
        <a key={s.id} className="btn btn-ghost btn-sm" href={s.href} target="_blank" rel="noopener noreferrer"
           onClick={() => trackEvent("share", { target: s.id })}>{s.label}</a>
      ))}
      <button type="button" className="btn btn-ghost btn-sm" onClick={copy}><Link2 size={13} /> {t("shareBar.copy")}</button>
    </div>
  );
}
