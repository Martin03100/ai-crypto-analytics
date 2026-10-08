/** Dashboard: the next few market events, with a link to the full calendar. */

import { ArrowRight, CalendarDays } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { daysUntil, eventName } from "../utils/calendar";
import { Card } from "./Card";

export default function UpcomingEvents({ style, limit = 3 }) {
  const { t, lang } = useLanguage();
  const [events, setEvents] = useState(null);
  useEffect(() => { api.calendar(30).then((d) => setEvents(d.events.slice(0, limit))).catch(() => setEvents([])); }, [limit]);
  if (!events || events.length === 0) return null;
  const locale = localeForLang(lang);
  return (
    <Card title={t("calendar.upcomingTitle")} icon={CalendarDays} style={style}>
      <ul className="upcoming-list">
        {events.map((e) => {
          const d = daysUntil(e.at);
          return (
            <li key={e.id}>
              <span className={`impact-dot impact-${e.impact}`} aria-hidden="true" />
              <span className="upcoming-name">{eventName(t, e)}</span>
              <span className="text-sub">
                {new Date(e.at).toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" })}
                {" · "}{d <= 0 ? t("calendar.today") : d === 1 ? t("calendar.tomorrow") : t("calendar.inDays", { n: d })}
              </span>
            </li>
          );
        })}
      </ul>
      <Link to="/calendar" className="text-link">{t("calendar.openFull")} <ArrowRight size={13} /></Link>
    </Card>
  );
}
