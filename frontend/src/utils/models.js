/** Model names as stored with evaluated forecasts, and mapping them to the provider list. */

export const QUANT_LABEL = "Quant (free model)";
export const CUSTOM_LABEL = "Custom (OpenAI-compatible)";

/** Display name of a stored model label in the UI language (`short` for tight spots like stat tiles). */
export function providerName(label, t, short = false) {
  if (label === QUANT_LABEL || label === "Statistical model") return t(short ? "provider.quantShort" : "provider.quantLabel");
  if (label === CUSTOM_LABEL) return t("provider.customLabel");
  return label;
}

export function providerForLabel(label, providers) {
  if (label === QUANT_LABEL) return providers.find((p) => p.provider === "quant");
  return providers.find((p) => p.label === label);
}

export function consensusInput(series) {
  return series
    .filter((s) => Number.isFinite(s.data?.aktualna_cena) && Number.isFinite(s.data?.ceny?.[s.data.ceny.length - 1]))
    .map((s) => ({ model: s.key === "quant" ? QUANT_LABEL : s.label, start: s.data.aktualna_cena, final: s.data.ceny[s.data.ceny.length - 1] }));
}
