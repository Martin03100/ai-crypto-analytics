/**
 * errorMessages.js
 * ==================
 * Prekladá chybové hlášky na krátke, zrozumiteľné vety pre bežného
 * používateľa, v aktuálne zvolenom jazyku aplikácie (en/sk/cs). Nikdy
 * nezobrazuje surové technické výpisy (stacktrace, HTTP detaily,
 * knižničné výnimky) — vždy iba preložený, ľudský text z translations.js.
 *
 * Dva zdroje chýb sa spracúvajú odlišne:
 *  1) Backend HTTPException.detail — sú to už krátke, zrozumiteľné vety
 *     (viď app/routers/*.py), ale iba v slovenčine. Nižšie ich PRESNE
 *     rozpoznáme podľa charakteristického úryvku a nahradíme preloženou
 *     verziou vo zvolenom jazyku (vrátane interpolácie čísel: sekundy,
 *     minúty zámky účtu a pod.).
 *  2) Surové chyby od AI providerov (Gemini/OpenAI/Anthropic/...) — tie
 *     obsahujú technické anglické texty a HTTP kódy (napr. "429 Too Many
 *     Requests"), preto sa rozpoznávajú regexom nad kľúčovými slovami/kódmi.
 */
import { translate } from "./translations";

// --- 1) Presné vzory pre known backend HTTPException.detail hlášky ---------
// `test` sa vyhodnocuje nad SUROVÝM textom z backendu (vždy slovenský zdroj,
// bez ohľadu na aktuálny jazyk appky) a prípadné capture groups sa mapujú
// na interpolačné parametre v `params`.
const KNOWN_BACKEND_PATTERNS = [
  { test: /neplatn[eé] alebo expirovan[eé] prihl[aá]senie/i, key: "errors.sessionExpired" },
  { test: /pr[ií]li[sš] ve[lľ]a po[zž]iadaviek.*?o (\d+)s/i, key: "errors.rateLimited", params: (m) => ({ seconds: m[1] }) },
  { test: /doč?asne uzamknut[yý].*?o (\d+) min/i, key: "errors.accountLocked", params: (m) => ({ minutes: m[1] }) },
  { test: /nespr[aá]vne pou[zž][ií]vate[lľ]sk[eé] meno alebo heslo/i, key: "errors.invalidCredentials" },
  { test: /pou[zž][ií]vate[lľ]sk[eé] meno je u[zž] obsaden[eé]/i, key: "errors.usernameTaken" },
  { test: /tento email u[zž] pou[zž][ií]va in[yý] [uú][cč]et/i, key: "errors.emailTaken" },
  { test: /k[oó]d je nespr[aá]vny alebo expirovan[yý]/i, key: "errors.invalidResetCode" },
  { test: /zadaj platn[uú] emailov[uú] adresu/i, key: "errors.invalidEmail" },
  { test: /aktu[aá]lne heslo nie je spr[aá]vne/i, key: "errors.wrongCurrentPassword" },
  { test: /nezn[aá]my ai provider/i, key: "errors.unknownProvider" },
  { test: /ulo[zž]en[aá] anal[yý]za nebola n[aá]jden[aá]/i, key: "errors.notFound" },
  { test: /csrf token/i, key: "errors.csrfInvalid" },
  { test: /nasta?la neo[cč]ak[aá]van[aá] chyba na serveri/i, key: "errors.serverError" },
  { test: /portf[oó]lio je pr[aá]zdne/i, key: "errors.emptyPortfolio" },
  { test: /[zž]iadne titulky na anal[yý]zu/i, key: "errors.noHeadlines" },
  { test: /[zž]iadna spr[aá]va na odoslanie/i, key: "errors.noChatMessage" },
  { test: /neplatn[aá] hodnota hlasu/i, key: "errors.invalidVote" },
  { test: /api kluc je pr[aá]zdny/i, key: "errors.emptyApiKey" },
  { test: /kluc sa nepodarilo overit/i, key: "errors.keyVerificationFailed" },
  { test: /najprv si over email/i, key: "errors.emailNotVerified" },
  { test: /zadaj 6-miestny k[oó]d z overovacej aplik/i, key: "errors.totpRequired" },
  { test: /nespr[aá]vny k[oó]d z overovacej aplik/i, key: "errors.totpInvalid" },
  { test: /overenie, [zž]e nie si robot/i, key: "errors.captchaFailed" },
  { test: /2fa u[zž] m[aá][sš] zapnut|najprv spusti nastavenie 2fa/i, key: "errors.totpSetupState" },
  { test: /na uk[aá][zž]kov[eé] d[aá]ta sa tipova[tť] ned[aá]/i, key: "errors.tipMock" },
  { test: /tipova[tť] sa d[aá] len do 2 hod[ií]n/i, key: "errors.tipWindowClosed" },
  { test: /na t[uú]to predikciu si u[zž] tipoval/i, key: "errors.tipAlreadyExists" },
  { test: /vlastn[eé]ho providera|vlastn[yý] provider (nie je spr[aá]vne|vr[aá]til presmerovanie)/i, key: "errors.customProviderInvalid" },
  // AI vratila prazdnu/orezanu/neplatnu odpoved (spravy z backend validatorov
  // a prazdnej Gemini odpovede) - predtym koncili ako vseobecne "Nieco sa pokazilo".
  { test: /pr[aá]zdn[uú] odpove[dď]|nepodarilo na[jĵ]?[sš]t [zž]iadny json|naparsovan[yý] json|pol(e|ia) '[^']+'.*mus[ií]/i, key: "errors.aiInvalidResponse" },
  { test: /najprv ulo[zž] api kl[uú][cč] pre tohto providera/i, key: "errors.noKeyToTest" },
];

// --- 2) Technické vzory pre surové chyby od AI providerov / siete ----------
const TECHNICAL_PATTERNS = [
  { test: /503|overloaded|service unavailable/i, key: "errors.providerOverloaded" },
  { test: /429|rate limit|too many requests/i, key: "errors.providerRateLimit" },
  { test: /401|unauthorized|invalid.?api.?key|incorrect api key/i, key: "errors.providerInvalidKey" },
  { test: /403|forbidden/i, key: "errors.providerForbidden" },
  // Zamerne VYZADUJE aj nazov/domenu AI providera vedla "404"/"not found" -
  // ina by tento vzor omylom chytil AJ generickú 404 z rozbiteho routingu
  // (napr. zle nastaveny Netlify proxy k backendu), ktora s AI providerom
  // vobec nesuvisi, a zavadzajuco by ju oznacil ako "chyba AI providera".
  { test: /(openai|anthropic|googleapis|gemini|deepseek|x\.ai|grok)[\s\S]{0,120}(404|not found)|(404|not found)[\s\S]{0,120}(openai|anthropic|googleapis|gemini|deepseek|x\.ai|grok)/i, key: "errors.providerNotFound" },
  { test: /timeout|timed out/i, key: "errors.timeout" },
  { test: /network|connection|econnrefused|failed to fetch/i, key: "errors.networkError" },
  { test: /insufficient_quota|quota|billing/i, key: "errors.providerQuota" },
  { test: /500|internal server error/i, key: "errors.serverError" },
];

/** Skusi rozpoznat chybu podla HTTP statusu (najspolahlivejsie, jazykovo
 * nezavisle). Vracia i18n kluc alebo null, ak status nie je jednoznacny. */
function keyFromStatus(status) {
  switch (status) {
    case 401: return "errors.sessionExpired";
    case 403: return "errors.csrfInvalid";
    case 422: return "errors.validationError";
    case 404: return "errors.routeNotFound";
    case 429: return "errors.rateLimited";
    case 500: case 502: case 504: return "errors.serverError";
    default: return null;
  }
}

/**
 * humanizeError(error, lang) -> preložený, krátky text pre používateľa.
 * `error` môže byť Error objekt (s `.message`, voliteľne `.status`) alebo
 * obyčajný string (spätná kompatibilita).
 */
export function humanizeError(error, lang = "en") {
  const rawMessage = typeof error === "string" ? error : error?.message;
  const status = typeof error === "object" && error !== null ? error.status : undefined;

  if (!rawMessage) return translate("errors.generic", lang);

  for (const pattern of KNOWN_BACKEND_PATTERNS) {
    const match = rawMessage.match(pattern.test);
    if (match) {
      const params = pattern.params ? pattern.params(match) : undefined;
      return translate(pattern.key, lang, params);
    }
  }

  for (const pattern of TECHNICAL_PATTERNS) {
    if (pattern.test.test(rawMessage)) {
      return translate(pattern.key, lang);
    }
  }

  // Ziadny textovy vzor sa nenasiel — skus aspon HTTP status kod.
  const statusKey = keyFromStatus(status);
  if (statusKey) return translate(statusKey, lang);

  // Uplny fallback: appka nikdy nezobrazi surovy technicky text (napr.
  // neznamu vynimku alebo JSON dump) - vzdy iba genericku prelozenu spravu.
  return translate("errors.generic", lang);
}

export default humanizeError;
