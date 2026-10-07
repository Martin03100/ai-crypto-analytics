/** Bell with the latest notifications: checked forecasts, finished duels and rewards. */

import { Bell } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { notificationText, timeAgo } from "../utils/notifications";

const POLL_MS = 120_000;

export default function NotificationBell() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [data, setData] = useState({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = useCallback(() => api.notifications().then(setData).catch(() => {}), []);
  useEffect(() => {
    load();
    const id = setInterval(() => { if (document.visibilityState === "visible") load(); }, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && data.unread > 0) {
      api.readNotifications().then(() => setData((prev) => ({ ...prev, unread: 0 }))).catch(() => {});
    }
  };

  const go = (n) => {
    setOpen(false);
    navigate(n.kind === "referral_reward" || n.kind === "premium_started" ? "/settings" : "/forecast?tab=history");
  };

  return (
    <div className="bell" ref={ref}>
      <button type="button" className="bell-btn" onClick={toggle} aria-expanded={open}
              aria-label={data.unread ? t("notif.labelUnread", { n: data.unread }) : t("notif.label")}>
        <Bell size={17} />
        {data.unread > 0 && <span className="bell-dot">{data.unread > 9 ? "9+" : data.unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label={t("notif.label")}>
          <div className="bell-head">{t("notif.label")}</div>
          {data.items.length === 0 ? (
            <p className="text-sub bell-empty">{t("notif.empty")}</p>
          ) : (
            <ul className="bell-list">
              {data.items.slice(0, 15).map((n) => (
                <li key={n.id}>
                  <button type="button" className={`bell-item ${n.read ? "" : "unread"}`} onClick={() => go(n)}>
                    <span>{notificationText(n, t)}</span>
                    <span className="text-sub bell-time">{n.created_at ? timeAgo(n.created_at, t) : ""}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
