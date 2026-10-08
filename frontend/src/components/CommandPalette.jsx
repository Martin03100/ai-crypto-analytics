/** Command palette (Ctrl+K / ⌘K): jump to a page, a coin or an action by typing a few letters. */

import { Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { useTheme } from "../context/ThemeContext";
import { useNavLinks } from "../hooks/useNavLinks";
import { useSimpleMode } from "../hooks/useSimpleMode";
import { LANGUAGES } from "../i18n/translations";
import { COINS } from "../utils/coins";
import { OPEN_PALETTE_EVENT, matches } from "../utils/viewHelpers";

export default function CommandPalette() {
  const { t, setLang } = useLanguage();
  const { toggleTheme } = useTheme();
  const { simple, setSimple } = useSimpleMode();
  const links = useNavLinks();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const returnFocus = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    const onOpen = () => setOpen(true);
    document.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_PALETTE_EVENT, onOpen);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_PALETTE_EVENT, onOpen);
    };
  }, []);

  useEffect(() => {
    if (open) {
      returnFocus.current = document.activeElement;
      setQuery("");
      setIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      returnFocus.current?.focus?.();
    }
  }, [open]);

  const close = useCallback(() => setOpen(false), []);

  const items = useMemo(() => {
    const go = (to) => () => navigate(to);
    const pages = [...links.main, ...links.extra, ...links.account].map((l) => ({
      id: `page:${l.to}`, group: t("palette.pages"), label: l.label, icon: l.icon, run: go(l.to),
    }));
    const coins = COINS.map((c) => ({ id: `coin:${c}`, group: t("palette.coins"), label: t("palette.forecastFor", { coin: c }), keywords: c, run: go(`/forecast?coin=${c}`) }));
    const actions = [
      { id: "act:theme", group: t("palette.actions"), label: t("palette.toggleTheme"), run: toggleTheme },
      { id: "act:simple", group: t("palette.actions"), label: t(simple ? "palette.simpleOff" : "palette.simpleOn"), run: () => setSimple(!simple) },
      ...LANGUAGES.map((l) => ({ id: `lang:${l.code}`, group: t("palette.actions"), label: `${t("palette.language")}: ${l.label}`, run: () => setLang(l.code) })),
    ];
    const all = [...pages, ...actions, ...coins];
    if (!query.trim()) return [...pages, ...actions];
    return all.filter((it) => matches(`${it.label} ${it.keywords || ""} ${it.group}`, query)).slice(0, 30);
  }, [links, navigate, t, toggleTheme, simple, setSimple, setLang, query]);

  useEffect(() => { setIndex(0); }, [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }, [index]);

  if (!open) return null;

  const run = (item) => {
    close();
    item?.run();
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIndex((i) => Math.min(i + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); run(items[index]); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
  };

  let lastGroup = null;
  return (
    <div className="confirm-overlay palette-overlay" onClick={close}>
      <div className="palette" role="dialog" aria-modal="true" aria-label={t("palette.title")} onClick={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <Search size={16} aria-hidden="true" />
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKeyDown}
                 placeholder={t("palette.placeholder")} aria-label={t("palette.placeholder")} role="combobox"
                 aria-expanded="true" aria-controls="palette-list" aria-activedescendant={items[index] ? `palette-${index}` : undefined}
                 autoComplete="off" spellCheck={false} />
          <kbd>Esc</kbd>
        </div>
        <ul className="palette-list" id="palette-list" role="listbox" ref={listRef}>
          {items.length === 0 && <li className="palette-empty">{t("palette.empty")}</li>}
          {items.map((item, i) => {
            const header = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            const Icon = item.icon;
            return [
              header && <li key={`h-${header}`} className="palette-group" role="presentation">{header}</li>,
              <li key={item.id} id={`palette-${i}`} data-index={i} role="option" aria-selected={i === index}
                  className={`palette-item ${i === index ? "active" : ""}`}
                  onMouseMove={() => setIndex(i)} onClick={() => run(item)}>
                {Icon ? <Icon size={15} aria-hidden="true" /> : <span className="palette-dot" aria-hidden="true" />}
                <span>{item.label}</span>
              </li>,
            ];
          })}
        </ul>
        <div className="palette-foot text-sub"><kbd>↑</kbd><kbd>↓</kbd> {t("palette.navigate")} · <kbd>Enter</kbd> {t("palette.open")}</div>
      </div>
    </div>
  );
}
