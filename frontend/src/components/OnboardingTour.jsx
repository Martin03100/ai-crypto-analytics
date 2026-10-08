/** Onboarding tour. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Gauge, Lightbulb } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useSimpleMode } from "../hooks/useSimpleMode";

const SEEN_KEY = "aca_onboarding_seen_v1";

function seenKey(userKey) {
  return userKey ? `${SEEN_KEY}:${userKey}` : SEEN_KEY;
}

const STEP_TARGETS = [
  { selector: ".fab-chat", titleKey: "onboarding.step1Title", textKey: "onboarding.step1Text" },
  { selector: 'a[href="/forecast"]', titleKey: "onboarding.step2Title", textKey: "onboarding.step2Text", needsSidebar: true },
  { selector: 'a[href="/portfolio"]', titleKey: "onboarding.step3Title", textKey: "onboarding.step3Text", needsSidebar: true },
  { selector: "#tour-feargreed-card", titleKey: "onboarding.step4Title", textKey: "onboarding.step4Text" },
  { selector: ".palette-trigger", titleKey: "onboarding.stepSearchTitle", textKey: "onboarding.stepSearchText", needsSidebar: true },
  { selector: 'a[href="/settings"]', titleKey: "onboarding.step5Title", textKey: "onboarding.step5Text", needsSidebar: true },
];

export function hasSeenOnboarding(userKey) {
  try {
    return localStorage.getItem(seenKey(userKey)) === "1";
  } catch {
    return true;
  }
}

function markOnboardingSeen(userKey) {
  try {
    localStorage.setItem(seenKey(userKey), "1");
  } catch {
  }
}

export function resetOnboarding(userKey) {
  try {
    localStorage.removeItem(seenKey(userKey));
  } catch {
  }
}

export default function OnboardingTour({ onNeedSidebar }) {
  const location = useLocation();
  const { t } = useLanguage();
  const { user } = useAuth();
  const userKey = user?.id ?? user?.username;
  const { chosen, setSimple } = useSimpleMode();
  const [choosing, setChoosing] = useState(false);
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const nextBtnRef = useRef(null);

  const finish = useCallback(() => {
    setActive(false);
    markOnboardingSeen(userKey);
    onNeedSidebar?.(false);
  }, [onNeedSidebar, userKey]);

  useEffect(() => {
    if (location.pathname !== "/dashboard" || !userKey) return;
    if (hasSeenOnboarding(userKey)) return;     // existing users switch the view on the dashboard or in Settings
    const timer = setTimeout(() => {
      if (!chosen) {
        setChoosing(true);   // first: beginner or full view, then the tour
        return;
      }
      setStepIndex(0);
      setActive(true);
    }, 700);
    return () => clearTimeout(timer);
  }, [location.pathname, userKey, chosen]);

  const choose = useCallback((simpleView) => {
    setChoosing(false);
    setSimple(simpleView);
    setStepIndex(0);
    setActive(true);
  }, [setSimple]);

  useEffect(() => {
    if (!choosing) return;
    const onKey = (e) => { if (e.key === "Escape") choose(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [choosing, choose]);

  const measure = useCallback(() => {
    const step = STEP_TARGETS[stepIndex];
    if (!step) return;
    const el = document.querySelector(step.selector);
    if (!el) {
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
      const t2 = setTimeout(measure, 150);
      return () => clearTimeout(t2);
    }
    onNeedSidebar?.(false);
    document.querySelector(step.selector)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
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

  if (choosing) {
    return (
      <div className="confirm-overlay" role="presentation">
        <div className="confirm-modal mode-choice" role="dialog" aria-modal="true" aria-labelledby="mode-choice-title">
          <h3 className="confirm-title" id="mode-choice-title">{t("viewMode.askTitle")}</h3>
          <p className="text-sub" style={{ marginTop: 0 }}>{t("viewMode.askLead")}</p>
          <div className="mode-options">
            <button type="button" className="mode-option" onClick={() => choose(true)} autoFocus>
              <Lightbulb size={20} aria-hidden="true" />
              <strong>{t("viewMode.beginner")}</strong>
              <span className="text-sub">{t("viewMode.beginnerText")}</span>
            </button>
            <button type="button" className="mode-option" onClick={() => choose(false)}>
              <Gauge size={20} aria-hidden="true" />
              <strong>{t("viewMode.advanced")}</strong>
              <span className="text-sub">{t("viewMode.advancedText")}</span>
            </button>
          </div>
          <p className="text-sub" style={{ marginBottom: 0 }}>{t("viewMode.later")}</p>
        </div>
      </div>
    );
  }

  if (!active) return null;

  const step = STEP_TARGETS[stepIndex];
  if (!step) return null;
  const isLast = stepIndex === STEP_TARGETS.length - 1;
  const pad = 8;
  const dockTop = rect && rect.bottom > window.innerHeight - 240;

  return (
    <div className="onboarding-layer" role="dialog" aria-modal="true" aria-label={t("onboarding.dialogLabel")}>
      {rect && (
        <div
          className="onboarding-hole"
          style={{ left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }}
        />
      )}
      <div className={`onboarding-tip onboarding-tip-docked${dockTop ? " onboarding-tip-docked-top" : ""}`}>
        <div className="onboarding-step-no">{t("onboarding.stepCounter", { current: stepIndex + 1, total: STEP_TARGETS.length })}</div>
        <h2>{t(step.titleKey)}</h2>
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
