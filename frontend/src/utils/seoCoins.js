/** Public coin pages for search engines: one per coin and language. Shared by the app and the edge function. */

export const SEO_COINS = [
  ["BTC", "bitcoin", "Bitcoin"], ["ETH", "ethereum", "Ethereum"], ["SOL", "solana", "Solana"], ["BNB", "bnb", "BNB"],
  ["XRP", "xrp", "XRP"], ["ADA", "cardano", "Cardano"], ["DOGE", "dogecoin", "Dogecoin"], ["AVAX", "avalanche", "Avalanche"],
  ["DOT", "polkadot", "Polkadot"], ["LINK", "chainlink", "Chainlink"], ["TON", "toncoin", "Toncoin"], ["TRX", "tron", "TRON"],
  ["LTC", "litecoin", "Litecoin"], ["BCH", "bitcoin-cash", "Bitcoin Cash"], ["SHIB", "shiba-inu", "Shiba Inu"],
  ["SUI", "sui", "Sui"], ["PEPE", "pepe", "Pepe"], ["NEAR", "near", "NEAR Protocol"], ["APT", "aptos", "Aptos"],
  ["UNI", "uniswap", "Uniswap"],
].map(([coin, slug, name]) => ({ coin, slug, name }));

export const SEO_LANGS = { en: "/prediction", sk: "/sk/predikcia", cs: "/cs/predikce", de: "/de/prognose", pl: "/pl/prognoza" };

export function coinBySlug(slug) {
  return SEO_COINS.find((c) => c.slug === String(slug || "").toLowerCase()) || null;
}

export function coinPath(lang, slug) {
  return `${SEO_LANGS[lang] || SEO_LANGS.en}/${slug}`;
}

export function langFromPath(pathname) {
  if (pathname.startsWith("/sk/")) return "sk";
  if (pathname.startsWith("/cs/")) return "cs";
  if (pathname.startsWith("/de/")) return "de";
  if (pathname.startsWith("/pl/")) return "pl";
  return "en";
}
