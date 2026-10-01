/** Supported coins: symbol -> CoinGecko id (mirrors DEFAULT_COIN_IDS in the backend config). */

export const COIN_IDS = {
  BTC: "bitcoin", ETH: "ethereum", SOL: "solana", BNB: "binancecoin", XRP: "ripple",
  ADA: "cardano", DOGE: "dogecoin", AVAX: "avalanche-2", DOT: "polkadot", LINK: "chainlink",
};

export const COINS = Object.keys(COIN_IDS);
