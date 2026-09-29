// Parse a portfolio CSV (generic "coin,amount" or an exchange balance export) into holdings.

export const MAX_CSV_BYTES = 200 * 1024;

const SYMBOL_HEADERS = ["coin", "asset", "symbol", "currency", "ticker", "token", "minca", "mena"];
// Ordered by preference: an exchange export's "Total" beats "Available"/"Free" (which excludes open orders).
const AMOUNT_HEADERS = ["total", "amount", "quantity", "qty", "balance", "holdings", "mnozstvo", "množstvo",
  "free", "available"];
const SYMBOL_RE = /^[A-Z0-9]{1,15}$/;

function detectDelimiter(line) {
  const counts = [",", ";", "\t"].map((d) => [d, line.split(d).length - 1]);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 0 ? counts[0][0] : ",";
}

// Minimal CSV field splitter with support for "quoted, fields" and "" escapes.
function splitLine(line, delimiter) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delimiter) { out.push(cur.trim()); cur = ""; }
    else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

function parseNumber(raw, delimiter) {
  let s = String(raw ?? "").replace(/\s/g, "");
  if (s === "") return null;
  // With ";" as delimiter the file is most likely from a comma-decimal locale ("0,5").
  if (delimiter !== "," && /^\d+,\d+$/.test(s)) s = s.replace(",", ".");
  else s = s.replace(/,(?=\d{3}(\D|$))/g, ""); // thousands separators: 1,234.5
  if (!/^\d*\.?\d+(e[+-]?\d+)?$/i.test(s)) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/**
 * @returns {{ holdings: Array<{symbol: string, amount: number}>, errors: Array<{line: number, reason: string}> }}
 * `reason` is an i18n key suffix: "symbol" | "amount" | "noColumns".
 */
export function parsePortfolioCsv(text) {
  const lines = String(text || "").replace(/^\uFEFF/, "").split(/\r?\n/).map((l) => l.trim());
  const firstIdx = lines.findIndex((l) => l !== "");
  if (firstIdx === -1) return { holdings: [], errors: [] };
  const delimiter = detectDelimiter(lines[firstIdx]);
  const header = splitLine(lines[firstIdx], delimiter).map((h) => h.toLowerCase());

  let symbolCol = header.findIndex((h) => SYMBOL_HEADERS.includes(h));
  let amountCol = -1;
  for (const name of AMOUNT_HEADERS) {
    amountCol = header.indexOf(name);
    if (amountCol !== -1) break;
  }
  let dataStart = firstIdx + 1;
  if (symbolCol === -1 && amountCol === -1) {
    // No header row: assume "symbol, amount".
    symbolCol = 0;
    amountCol = 1;
    dataStart = firstIdx;
  } else if (symbolCol === -1 || amountCol === -1) {
    return { holdings: [], errors: [{ line: firstIdx + 1, reason: "noColumns" }] };
  }

  const totals = new Map();
  const errors = [];
  for (let i = dataStart; i < lines.length; i += 1) {
    if (lines[i] === "") continue;
    const cells = splitLine(lines[i], delimiter);
    const symbol = (cells[symbolCol] || "").toUpperCase();
    const amount = parseNumber(cells[amountCol], delimiter);
    if (!SYMBOL_RE.test(symbol)) { errors.push({ line: i + 1, reason: "symbol" }); continue; }
    if (amount === null) { errors.push({ line: i + 1, reason: "amount" }); continue; }
    if (amount === 0) continue; // empty balances in exchange exports are not holdings
    totals.set(symbol, (totals.get(symbol) || 0) + amount);
  }
  return { holdings: [...totals].map(([symbol, amount]) => ({ symbol, amount })), errors };
}
