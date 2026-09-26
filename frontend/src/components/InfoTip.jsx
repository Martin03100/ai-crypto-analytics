import { Info } from "lucide-react";
import { useId, useState } from "react";

/** Mala ikonka (i) s vysvetlenim pojmu - na hover/focus (PC) aj tuknutie (mobil). */
export default function InfoTip({ text }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="infotip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="infotip-btn" aria-label={text} aria-describedby={open ? id : undefined}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((v) => !v); }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
        <Info size={12} />
      </button>
      {open && <span role="tooltip" id={id} className="infotip-bubble">{text}</span>}
    </span>
  );
}
