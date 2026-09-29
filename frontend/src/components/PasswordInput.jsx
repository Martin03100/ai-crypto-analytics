/** Password input. */

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { useLanguage } from "../context/LanguageContext";

export default function PasswordInput({ value, onChange, placeholder, className = "input", autoComplete = "current-password" }) {
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
        autoComplete={autoComplete}
        maxLength={128}
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
