/** Price labels are stored like "€4.99 / month"; the period is shown in the reader's language. */

export function localizePriceLabel(label, t) {
  if (!label) return label;
  return String(label)
    .replace(/\/\s*month$/i, `/ ${t("premium.perMonth")}`)
    .replace(/\/\s*year$/i, `/ ${t("premium.perYear")}`);
}
