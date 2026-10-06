/** Premium waitlist sign-up (no account needed). */

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { getUtmSource, trackEvent } from "../utils/analytics";

export default function WaitlistForm({ id = "waitlist" }) {
  const { t, lang } = useLanguage();
  const [email, setEmail] = useState("");
  const [state, setState] = useState("idle"); // idle | sending | done | error

  const submit = async (e) => {
    e.preventDefault();
    setState("sending");
    try {
      await api.joinWaitlist(email.trim(), lang, getUtmSource());
      setState("done");
      trackEvent("waitlist-signup", { source: getUtmSource() || "direct" });
    } catch {
      setState("error");
    }
  };

  return (
    <section id={id} className="card landing-waitlist" aria-labelledby={`${id}-title`}>
      <div className="landing-feature-icon"><Sparkles size={18} /></div>
      <h2 id={`${id}-title`}>{t("waitlist.title")}</h2>
      <p className="text-sub">{t("waitlist.text")}</p>
      {state === "done" ? (
        <p className="waitlist-success" role="status">{t("waitlist.success")}</p>
      ) : (
        <form className="waitlist-form" onSubmit={submit}>
          <input
            className="input"
            type="email"
            required
            maxLength={255}
            autoComplete="email"
            placeholder={t("waitlist.placeholder")}
            aria-label={t("waitlist.placeholder")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={state === "sending"}>{t("waitlist.submit")}</button>
        </form>
      )}
      {state === "error" && <p className="waitlist-error" role="alert">{t("waitlist.error")}</p>}
      <p className="text-sub waitlist-consent">{t("waitlist.consent")}</p>
    </section>
  );
}
