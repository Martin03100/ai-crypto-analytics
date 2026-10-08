/** Browser notifications: switch on for this device and choose what to be told about. */

import { BellRing, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { currentSubscription, disablePush, enablePush, needsInstallForPush, pushSupported } from "../utils/pushClient";
import { Card } from "./Card";

const CATEGORIES = ["alerts", "flips", "results", "events"];

export default function NotificationSettings() {
  const { t } = useLanguage();
  const { push } = useToast();
  const [prefs, setPrefs] = useState(null);
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const supported = pushSupported();
  const denied = supported && Notification.permission === "denied";

  const load = useCallback(() => {
    api.notifyPrefs().then((r) => setPrefs(r.prefs)).catch(() => setPrefs({ alerts: true, flips: true, results: true, events: true }));
    currentSubscription().then((s) => setOn(Boolean(s))).catch(() => setOn(false));
  }, []);
  useEffect(load, [load]);

  const toggleDevice = async () => {
    setBusy(true);
    try {
      if (on) {
        await disablePush();
        setOn(false);
        push(t("notify.offDone"), "success", { translated: true });
      } else {
        const res = await enablePush();
        if (res === "on") {
          setOn(true);
          push(t("notify.onDone"), "success", { translated: true });
        } else {
          push(t(res === "denied" ? "notify.denied" : "notify.unsupported"), "error", { translated: true });
        }
      }
    } catch (err) {
      push(err?.message || t("notify.failed"), "error", { translated: !err?.message });
    } finally {
      setBusy(false);
    }
  };

  const toggleCategory = async (key) => {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    try {
      setPrefs((await api.setNotifyPrefs({ [key]: next[key] })).prefs);
    } catch (err) {
      setPrefs(prefs);
      push(err?.message || "error", "error");
    }
  };

  const test = async () => {
    try {
      const r = await api.pushTest();
      push(t(r.sent ? "notify.testSent" : "notify.testFailed"), r.sent ? "success" : "error", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  return (
    <Card title={t("notify.title")} icon={BellRing} id="notifications">
      <p className="text-sub" style={{ marginTop: 0 }}>{t("notify.lead")}</p>
      {!supported ? (
        <p className="text-sub">{t(needsInstallForPush() ? "notify.iosInstall" : "notify.unsupported")}</p>
      ) : (
        <div className="notify-device">
          <label className="toggle-row">
            <input type="checkbox" checked={on} disabled={busy || (denied && !on)} onChange={toggleDevice} />
            <span><strong>{t("notify.device")}</strong>
              <span className="text-sub" style={{ display: "block" }}>{denied && !on ? t("notify.deniedHelp") : t("notify.deviceText")}</span>
            </span>
          </label>
          {on && <button type="button" className="btn btn-ghost btn-sm" onClick={test}><Send size={13} /> {t("notify.test")}</button>}
        </div>
      )}
      {prefs && (
        <fieldset className="notify-cats">
          <legend className="text-sub">{t("notify.what")}</legend>
          {CATEGORIES.map((c) => (
            <label key={c} className="toggle-row">
              <input type="checkbox" checked={Boolean(prefs[c])} onChange={() => toggleCategory(c)} />
              <span><strong>{t(`notify.cat_${c}`)}</strong><span className="text-sub" style={{ display: "block" }}>{t(`notify.cat_${c}Text`)}</span></span>
            </label>
          ))}
        </fieldset>
      )}
    </Card>
  );
}
