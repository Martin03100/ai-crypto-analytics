/** Small helpers over a saved forecast's data (`ceny` = forecast prices, `aktualna_cena` = price at creation). */

export function finalForecastPrice(data) {
  const prices = Array.isArray(data?.ceny) ? data.ceny.filter(Number.isFinite) : [];
  return prices.length ? prices[prices.length - 1] : null;
}

/** Predicted move from the price at forecast time to the last forecast point, in %. */
export function predictedChangePct(data) {
  const final = finalForecastPrice(data);
  const start = Number(data?.aktualna_cena);
  if (final == null || !Number.isFinite(start) || start <= 0) return null;
  return ((final - start) / start) * 100;
}
