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
  { selector: ".fab-chat", titleKey: "onboarding.step1Title", textKey: "onboarding.step1Text" },
  { selector: 'a[href="/forecast"]', titleKey: "onboarding.step2Title", textKey: "onboarding.step2Text", needsSidebar: true },
  { selector: 'a[href="/portfolio"]', titleKey: "onboarding.step3Title", textKey: "onboarding.step3Text", needsSidebar: true },
  { selector: "#tour-feargreed-card", titleKey: "onboarding.step4Title", textKey: "onboarding.step4Text" },
  { selector: 'a[href="/settings"]', titleKey: "onboarding.step5Title", textKey: "onboarding.step5Text", needsSidebar: true },
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
 *
 * DOLEZITE (poucenie z realneho bugu): tooltip textu/tlacidlam je VZDY
 * pripnuty na pevne miesto dole na obrazovke (nie dynamicky vedla ciela) -
 * pri dynamickom pozicovani vedla ciela sa mohlo stat, ze ak bol cielovy
 * prvok nizko na dlhej stranke, tooltip (aj s tlacidlami Dalej/Preskocit) sa
 * odrezal mimo viditelnej plochy a strankou sa neda scrollovat (fixed prvky
 * sa scrollom nehybu) - pouzivatel sa tak realne zasekol v ture bez moznosti
 * pokracovat. Pevne dolne miesto tomuto zaruku vylucuje: text/tlacidla su VZDY
 * v ramci viewportu, bez ohladu na to, kde presne je cielovy prvok. Cielovy
 * prvok sa navyse pri kazdom kroku scrollne do viditelnej casti, aby
 * pouzivatel videl aj samotne zvyraznenie (spotlight), nie len text o nom.
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
    // Nech je zvyrazneny prvok skutocne vidiet (nie len tooltip o nom) -
    // "nearest" nehybe strankou, ak uz je prvok viditelny.
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
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

  if (!active) return null;

  const step = STEP_TARGETS[stepIndex];
  if (!step) return null;
  const isLast = stepIndex === STEP_TARGETS.length - 1;
  const pad = 8;

  return (
    <div className="onboarding-layer" role="dialog" aria-modal="true" aria-label={t("onboarding.dialogLabel")}>
      {rect && (
        <div
          className="onboarding-hole"
          style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}
        />
      )}
      {/* Pevne pripnute dole na obrazovke (nikdy nie dynamicky vedla ciela) -
         tlacidla Dalej/Preskocit su tak VZDY v ramci viewportu, bez ohladu na
         to, kde je cielovy prvok na stranke. */}
      <div className="onboarding-tip onboarding-tip-docked">
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
