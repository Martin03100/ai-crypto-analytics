/** Skopiruje text do schranky. Pouziva navigator.clipboard (vyzaduje HTTPS
 * alebo localhost); ak zlyha/nie je dostupne, padne na fallback cez docasny
 * textarea + document.execCommand. Vracia Promise<boolean> (uspech). */
export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // padni na fallback nizsie
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}
