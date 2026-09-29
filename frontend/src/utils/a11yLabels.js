/** Form label linking. */

let seq = 0;
const CONTROL = "input:not([type=hidden]), select, textarea";

export function associateLabels(root = document) {
  root.querySelectorAll(".field > label").forEach((label) => {
    if (label.control && label.parentElement.contains(label.control)) return;
    const control = label.parentElement.querySelector(CONTROL);
    if (!control) return;
    if (!control.id) { seq += 1; control.id = `aca-field-${seq}`; }
    label.htmlFor = control.id;
  });
}

export function startLabelAssociation() {
  if (typeof MutationObserver === "undefined" || typeof document === "undefined") return () => {};
  let scheduled = false;
  const run = () => { scheduled = false; associateLabels(); };
  const observer = new MutationObserver(() => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(run); }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  associateLabels();
  return () => observer.disconnect();
}
