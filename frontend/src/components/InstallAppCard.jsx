/** Settings card: install the app (PWA) on the device. */

import { Download, Share, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { PWA_INSTALLABLE_EVENT, canPromptInstall, isIosSafari, isStandalone, promptInstall } from "../pwa";
import { Card } from "./Card";

export default function InstallAppCard() {
  const { t } = useLanguage();
  const [installable, setInstallable] = useState(canPromptInstall);
  const [installed, setInstalled] = useState(isStandalone);

  useEffect(() => {
    const onInstallable = () => setInstallable(true);
    const onInstalled = () => { setInstalled(true); setInstallable(false); };
    window.addEventListener(PWA_INSTALLABLE_EVENT, onInstallable);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener(PWA_INSTALLABLE_EVENT, onInstallable);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  async function install() {
    const accepted = await promptInstall();
    setInstallable(canPromptInstall());
    if (accepted) setInstalled(true);
  }

  let body;
  if (installed) body = <p className="text-sub">{t("pwa.installed")}</p>;
  else if (installable) {
    body = (
      <>
        <p className="text-sub">{t("pwa.installText")}</p>
        <button className="btn btn-primary" onClick={install}><Download size={15} /> {t("pwa.installButton")}</button>
      </>
    );
  } else if (isIosSafari()) {
    body = <p className="text-sub">{t("pwa.iosText")} <Share size={13} style={{ verticalAlign: -2 }} aria-hidden="true" /></p>;
  } else body = <p className="text-sub">{t("pwa.browserText")}</p>;

  return (
    <Card title={t("pwa.title")} icon={Smartphone}>
      <div className="install-row">{body}</div>
      <p className="field-hint" style={{ margin: "12px 0 0" }}>{t("pwa.offlineNote")}</p>
    </Card>
  );
}
