/** One-click unsubscribe from the weekly email (link from the email itself). */

import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Unsubscribe() {
  const { t } = useLanguage();
  const [params] = useSearchParams();
  const [state, setState] = useState("working");
  usePageTitle("unsubscribe.title");

  useEffect(() => {
    const userId = Number(params.get("u"));
    const token = params.get("t") || "";
    if (!Number.isInteger(userId) || userId < 1 || token.length < 16) {
      setState("invalid");
      return;
    }
    api.unsubscribeDigest(userId, token).then(() => setState("done")).catch(() => setState("invalid"));
  }, [params]);

  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("unsubscribe.title")}</h1>
      <p role="status">{t(`unsubscribe.${state}`)}</p>
    </main>
  );
}
