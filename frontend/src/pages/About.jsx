/** About the project: purpose, architecture, technologies and data sources. */

import { ArrowLeft, Boxes, Database, ExternalLink, FlaskConical, GraduationCap, ShieldCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

const REPO_URL = "https://github.com/Martin03100/ai-crypto-analytics";

const STACK = [
  ["Frontend", "React 18, Vite, React Router, Recharts"],
  ["Backend", "Python, FastAPI, SQLAlchemy, Pydantic"],
  ["Database", "PostgreSQL (production), SQLite (development)"],
  ["AI", "Google Gemini, OpenAI, Anthropic Claude, DeepSeek, xAI Grok, OpenAI-compatible APIs"],
  ["Testing", "pytest, Vitest, Playwright (end-to-end), GitHub Actions CI"],
  ["Hosting", "Netlify (frontend), Render (backend)"],
];

const SOURCES = [
  ["CoinGecko", "https://www.coingecko.com/en/api", "about.source.coingecko"],
  ["Alternative.me Fear & Greed", "https://alternative.me/crypto/fear-and-greed-index/", "about.source.feargreed"],
  ["Blockchair", "https://blockchair.com/api", "about.source.blockchair"],
  ["CoinDesk, Cointelegraph, Decrypt (RSS)", "https://www.coindesk.com/", "about.source.news"],
  ["Federal Reserve, U.S. BLS", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "about.source.macro"],
];

const LAYERS = ["about.arch.browser", "about.arch.api", "about.arch.services", "about.arch.external"];

export default function About() {
  const { t } = useLanguage();
  usePageTitle("about.title");
  return (
    <main className="standalone-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> {t("share.backToApp")}</Link>
      <h1 className="standalone-title">{t("about.title")}</h1>
      <p style={{ lineHeight: 1.7, marginBottom: 20 }}>{t("about.intro")}</p>

      <Card title={t("about.featuresTitle")} icon={Sparkles}>
        <ul className="about-list">
          {["forecast", "quant", "backtest", "portfolio", "market", "community", "security"].map((k) => <li key={k}>{t(`about.feature.${k}`)}</li>)}
        </ul>
      </Card>

      <Card title={t("about.archTitle")} icon={Boxes} style={{ marginTop: 16 }}>
        <div className="arch-diagram" role="img" aria-label={t("about.archAlt")}>
          {LAYERS.map((key, i) => (
            <div key={key} className="arch-layer-wrap">
              <div className="arch-layer"><strong>{t(`${key}.name`)}</strong><span className="text-sub">{t(`${key}.desc`)}</span></div>
              {i < LAYERS.length - 1 && <div className="arch-arrow" aria-hidden="true">↓</div>}
            </div>
          ))}
        </div>
      </Card>

      <Card title={t("about.stackTitle")} icon={Database} style={{ marginTop: 16 }}>
        <div className="about-table">
          {STACK.map(([k, v]) => <div key={k} className="about-row"><strong>{k}</strong><span>{v}</span></div>)}
        </div>
      </Card>

      <Card title={t("about.sourcesTitle")} icon={ExternalLink} style={{ marginTop: 16 }}>
        <div className="about-table">
          {SOURCES.map(([name, url, key]) => (
            <div key={name} className="about-row">
              <a href={url} target="_blank" rel="noreferrer" className="key-link">{name}</a>
              <span>{t(key)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card title={t("about.qualityTitle")} icon={FlaskConical} style={{ marginTop: 16 }}>
        <p className="text-sub" style={{ lineHeight: 1.7 }}>{t("about.quality")}</p>
        <div style={{ display: "flex", gap: 14, marginTop: 10, flexWrap: "wrap" }}>
          <Link to="/status" className="key-link">{t("status.title")}</Link>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="key-link">GitHub <ExternalLink size={11} /></a>
        </div>
      </Card>

      <Card title={t("about.securityTitle")} icon={ShieldCheck} style={{ marginTop: 16 }}>
        <p className="text-sub" style={{ lineHeight: 1.7 }}>{t("about.security")}</p>
      </Card>

      <Card title={t("about.authorTitle")} icon={GraduationCap} style={{ marginTop: 16 }}>
        <p className="text-sub" style={{ lineHeight: 1.7 }}>{t("about.author")}</p>
      </Card>

      <p className="text-sub standalone-disclaimer">{t("share.disclaimer")}</p>
    </main>
  );
}
