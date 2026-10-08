/** Browser (Web Push) notifications: permission, subscription and the server registration. */

import { api } from "../api";

export function pushSupported() {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** iPhone / iPad allow web push only for apps added to the home screen. */
export function needsInstallForPush() {
  if (typeof navigator === "undefined") return false;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
  return ios && !standalone;
}

export function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** True when the browser subscription was made with this server key (unknown keys count as matching). */
export function sameKey(buffer, key) {
  if (!buffer) return true;
  const a = new Uint8Array(buffer);
  return a.length === key.length && a.every((v, i) => v === key[i]);
}

async function registration() {
  if (!pushSupported()) return null;
  return Promise.race([navigator.serviceWorker.ready, new Promise((resolve) => setTimeout(() => resolve(null), 4000))]);
}

export async function currentSubscription() {
  const reg = await registration();
  return reg ? reg.pushManager.getSubscription() : null;
}

/** Ask for permission (if needed), subscribe and tell the server. Returns "on", "denied" or "unsupported". */
export async function enablePush() {
  const reg = await registration();
  if (!reg) return "unsupported";
  const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
  if (permission !== "granted") return "denied";
  const { key } = await api.pushKey();
  const serverKey = urlBase64ToUint8Array(key);
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub.options?.applicationServerKey, serverKey)) {
    await sub.unsubscribe().catch(() => {});      // made with older server keys: push services would reject it
    sub = null;
  }
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: serverKey });
  const json = sub.toJSON();
  await api.pushSubscribe({ endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } });
  return "on";
}

/** Unsubscribe this browser (on the server first, so a failed local step never leaves pushes flowing). */
export async function disablePush() {
  const sub = await currentSubscription();
  if (!sub) return;
  await api.pushUnsubscribe(sub.endpoint).catch(() => {});
  await sub.unsubscribe().catch(() => {});
}
