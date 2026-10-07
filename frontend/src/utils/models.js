/** Model names as stored with evaluated forecasts, and mapping them to the provider list. */

export const QUANT_LABEL = "Quant (free model)";

export function providerForLabel(label, providers) {
  if (label === QUANT_LABEL) return providers.find((p) => p.provider === "quant");
  return providers.find((p) => p.label === label);
}

export function consensusInput(series) {
  return series
    .filter((s) => Number.isFinite(s.data?.aktualna_cena) && Number.isFinite(s.data?.ceny?.[s.data.ceny.length - 1]))
    .map((s) => ({ model: s.key === "quant" ? QUANT_LABEL : s.label, start: s.data.aktualna_cena, final: s.data.ceny[s.data.ceny.length - 1] }));
}
