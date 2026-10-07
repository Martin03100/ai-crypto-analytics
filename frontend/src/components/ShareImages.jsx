/** Download or share a forecast as an image: 9:16 story (Instagram / TikTok) or 1:1 post. */

import { Image as ImageIcon, Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { trackEvent } from "../utils/analytics";

export default function ShareImages({ token, coin = "forecast" }) {
  const { t } = useLanguage();
  const { push } = useToast();
  const [busy, setBusy] = useState(null);

  const get = async (fmt) => {
    setBusy(fmt);
    try {
      const res = await fetch(api.shareCardUrl(token, fmt));
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const file = new File([blob], `ai-crypto-${coin.toLowerCase()}-${fmt}.png`, { type: "image/png" });
      trackEvent("share-image", { fmt });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], url: `${window.location.origin}/share/${token}` }).catch(() => {});
      } else {
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement("a"), { href: url, download: file.name });
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch {
      push(t("shareImage.failed"), "error", { translated: true });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="share-images">
      <span className="text-sub">{t("shareImage.label")}</span>
      {["story", "square"].map((fmt) => (
        <button key={fmt} type="button" className="btn btn-ghost btn-sm" onClick={() => get(fmt)} disabled={busy !== null}>
          {busy === fmt ? <Loader2 size={13} className="spin" /> : <ImageIcon size={13} />} {t(`shareImage.${fmt}`)}
        </button>
      ))}
    </div>
  );
}
