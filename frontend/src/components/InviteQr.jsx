/** QR code of the invite link, e.g. for a video or a poster; generated in the browser. */

import { Download, QrCode } from "lucide-react";
import { useState } from "react";
import { useLanguage } from "../context/LanguageContext";

export default function InviteQr({ link }) {
  const { t } = useLanguage();
  const [src, setSrc] = useState(null);
  const [failed, setFailed] = useState(false);

  const show = async () => {
    try {
      const QRCode = (await import("qrcode")).default;
      setSrc(await QRCode.toDataURL(link, { margin: 1, width: 360, color: { dark: "#0b0b0f", light: "#ffffff" } }));
    } catch {
      setFailed(true);
    }
  };

  if (!src) {
    return (
      <button type="button" className="btn btn-ghost btn-sm" onClick={show} disabled={failed}>
        <QrCode size={13} /> {t("invite.qrShow")}
      </button>
    );
  }
  return (
    <div className="invite-qr">
      <img src={src} alt={t("invite.qrAlt")} width={180} height={180} />
      <a className="btn btn-ghost btn-sm" href={src} download="ai-crypto-analytics-invite.png"><Download size={13} /> {t("invite.qrDownload")}</a>
    </div>
  );
}
