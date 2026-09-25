import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";

/** localStorage kluc - ked je nastaveny, sprievodca sa uz nikdy znova
 * automaticky nespusti (viz aj Settings.jsx "Spustit sprievodcu znova"). */
const SEEN_KEY = "aca_onboarding_seen_v1";

/** Poradie krokov + CSS selektor cielového prvku pre kazdy z nich. Selektory
 * mieria na uz existujuce, stabilne triedy/atributy (nie na text), takze
 * preklad ani zmena poradia menu polozky sprievodcu nerozbije. */
const STEP_TARGETS = [
  { selector: ".fab-chat", titleKey: "onboarding.step1Title", textKey: "onboarding.step1Text", pos: "left" },
  { selector: 'a[href="/forecast"]', titleKey: "onboarding.step2Title", textKey: "onboarding.step2Text", pos: "right", needsSidebar: true },
  { selector: 'a[href="/portfolio"]', titleKey: "onboarding.step3Title", textKey: "onboarding.step3Text", pos: "right", needsSidebar: true },
  { selector: "#tour-feargreed-card", titleKey: "onboarding.step4Title", textKey: "onboarding.step4Text", pos: "bottom" },
  { selector: 'a[href="/settings"]', titleKey: "onboarding.step5Title", textKey: "onboarding.step5Text", pos: "right", needsSidebar: true },
];

export function hasSeenOnboarding() {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return true; // ak localStorage nie je dostupny (private mode a pod.), radsej sprievodcu vobec neukazuj
  }
}

function markOnboardingSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // ticho ignorovat - nie je to kriticke, len sa sprievodca priste ukaze znova
  }
}

/** Vratane exportu na rucne znovu-spustenie z Settings.jsx ("Spustit sprievodcu znova"). */
export function resetOnboarding() {
  try {
    localStorage.removeItem(SEEN_KEY);
  } catch {
    // ignorovat
  }
}

/**
 * Onboarding sprievodca - spotlight + tooltip krokovac, co sa spusti presne
 * raz (pri prvom pristati na /dashboard po prihlaseni). Mounted v Layout.jsx,
 * takze ma pristup ku vsetkym cielovym prvkom (sidebar, chat FAB) aj naprieč
 * strankami cez position:fixed prekryvnu vrstvu (nie je vazany na jeden
 * konkretny rodicovsky kontajner).
 */
export default function OnboardingTour({ onNeedSidebar }) {
  const location = useLocation();
  const { t } = useLanguage();
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const nextBtnRef = useRef(null);

  const finish = useCallback(() => {
    setActive(false);
    markOnboardingSeen();
    onNeedSidebar?.(false);
  }, [onNeedSidebar]);

  // Auto-spustenie: len raz, len na /dashboard, len ak este nebolo videne.
  // "Spustit sprievodcu znova" v Settings.jsx zavola resetOnboarding() a
  // presmeruje na /dashboard - tento efekt to potom prirodzene znova
  // odchyti presne tou istou cestou ako pri prvom prihlaseni.
  useEffect(() => {
    if (location.pathname !== "/dashboard") return;
    if (hasSeenOnboarding()) return;
    // Kratke oneskorenie - nech Dashboard staci nacitat data (Fear&Greed
    // karta sa objavi az po fetch-i), inak by prvy krok mieril do prazdna.
    const timer = setTimeout(() => {
      setStepIndex(0);
      setActive(true);
    }, 700);
    return () => clearTimeout(timer);
  }, [location.pathname]);

  const measure = useCallback(() => {
    const step = STEP_TARGETS[stepIndex];
    if (!step) return;
    const el = document.querySelector(step.selector);
    if (!el) {
      // cielovy prvok (este) neexistuje - preskoc na dalsi krok namiesto
      // toho, aby sprievodca ukazoval prazdne miesto
      setStepIndex((i) => (i + 1 < STEP_TARGETS.length ? i + 1 : -1));
      return;
    }
    setRect(el.getBoundingClientRect());
  }, [stepIndex]);

  useEffect(() => {
    if (!active) return;
    if (stepIndex === -1) {
      finish();
      return;
    }
    const step = STEP_TARGETS[stepIndex];
    if (step?.needsSidebar) {
      onNeedSidebar?.(true);
      // Mobilny sidebar sa objavi prepnutim display:none -> flex (nie
      // animovanym transformom), takze staci kratka pauza na commit DOM-u
      // a preklad rozlozenia, nie plna dlzka prechodovej animacie.
      const t2 = setTimeout(measure, 150);
      return () => clearTimeout(t2);
    }
    onNeedSidebar?.(false);
    measure();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, stepIndex]);

  useEffect(() => {
    if (!active || stepIndex === -1) return;
    nextBtnRef.current?.focus();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [active, stepIndex, measure]);

  useEffect(() => {
    if (!active) return;
    function onKey(e) {
      if (e.key === "Escape") finish();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [active, finish]);

  if (!active || !rect) return null;

  const step = STEP_TARGETS[stepIndex];
  const isLast = stepIndex === STEP_TARGETS.length - 1;
  const pad = 8;
  const tw = 272;

  let tipStyle = {};
  if (step.pos === "right") {
    tipStyle = { left: rect.right + 18, top: Math.max(12, rect.top - 6) };
  } else if (step.pos === "left") {
    tipStyle = { left: Math.max(12, rect.left - tw - 18), top: Math.max(12, rect.top - 100) };
  } else {
    tipStyle = { left: Math.max(12, Math.min(rect.left, window.innerWidth - tw - 12)), top: rect.bottom + 16 };
  }

  return (
    <div className="onboarding-layer" role="dialog" aria-modal="true" aria-label={t("onboarding.dialogLabel")}>
      <div
        className="onboarding-hole"
        style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}
      />
      <div className="onboarding-tip" style={tipStyle}>
        <div className="onboarding-step-no">{t("onboarding.stepCounter", { current: stepIndex + 1, total: STEP_TARGETS.length })}</div>
        <h4>{t(step.titleKey)}</h4>
        <p aria-live="polite">{t(step.textKey)}</p>
        <div className="onboarding-actions">
          <button type="button" className="btn-skip-tour" onClick={finish}>{t("onboarding.skip")}</button>
          <button type="button" ref={nextBtnRef} className="btn-next-tour" onClick={() => (isLast ? finish() : setStepIndex((i) => i + 1))}>
            {isLast ? t("onboarding.finish") : t("onboarding.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
