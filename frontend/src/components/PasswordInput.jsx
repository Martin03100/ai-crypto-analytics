import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { useLanguage } from "../context/LanguageContext";

/** Heslovy <input> s prepinacom viditelnosti (oko ikonka) - pouzivatel si
 * vie overit, ze si heslo nepreklepol, bez toho, aby ho niekto pri pohlade
 * cez rameno videl trvalo (predvolene je vzdy skryte, zobrazenie je aktivna
 * volba). Pouzite vsade, kde appka pyta heslo (Auth.jsx, Settings.jsx). */
export default function PasswordInput({ value, onChange, placeholder, className = "input" }) {
  const [visible, setVisible] = useState(false);
  const { t } = useLanguage();
  return (
    <div className="password-input-wrap">
      <input
        className={className}
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
      />
      <button
        type="button"
        className="password-toggle-btn"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? t("common.hidePassword") : t("common.showPassword")}
        tabIndex={0}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
