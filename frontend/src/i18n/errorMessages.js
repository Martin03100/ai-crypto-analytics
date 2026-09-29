/** API error translations. */

import { translate } from "./translations";

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
  { test: /pr[aá]zdn[uú] odpove[dď]|nepodarilo na[jĵ]?[sš]t [zž]iadny json|naparsovan[yý] json|chyba pri parsovan[ií] json|ch[yý]baj[uú]ce k[lľ][uú][cč]e|pol(e|ia) '[^']+'.*(mus[ií]|smie)|ai vr[aá]tila \d+ bodov|odpor[uú][cč]anie \d+|sektor '[^']+' nem[aá]/i, key: "errors.aiInvalidResponse" },
  { test: /najprv ulo[zž] api kl[uú][cč] pre tohto providera/i, key: "errors.noKeyToTest" },
  { test: /pou[zž][ií]vate[lľ]sk[eé] meno mus[ií] ma[tť] 3/i, key: "errors.usernameInvalid" },
  { test: /predikciu sa nepodarilo overi[tť]/i, key: "errors.forecastUnverified" },
  { test: /bezplatn[yý] model|chyba pri na[cč][ií]tan[ií] historick[yý]ch d[aá]t|nedostatok historick[yý]ch d[aá]t|trhov[eé] d[aá]ta moment[aá]lne|trhove data sa nepodarilo/i, key: "errors.quantUnavailable" },
];

const TECHNICAL_PATTERNS = [
  { test: /api[ _-]?key[ _-]?(not valid|invalid)|api_key_invalid|permission_denied|invalid x-api-key|authentication/i, key: "errors.providerInvalidKey" },
  { test: /name resolution|getaddrinfo|nodename nor servname|max retries exceeded|proxyerror/i, key: "errors.networkError" },
  { test: /503|overloaded|service unavailable/i, key: "errors.providerOverloaded" },
  { test: /429|rate limit|too many requests/i, key: "errors.providerRateLimit" },
  { test: /401|unauthorized|invalid.?api.?key|incorrect api key/i, key: "errors.providerInvalidKey" },
  { test: /403|forbidden/i, key: "errors.providerForbidden" },
  { test: /(openai|anthropic|googleapis|gemini|deepseek|x\.ai|grok)[\s\S]{0,120}(404|not found)|(404|not found)[\s\S]{0,120}(openai|anthropic|googleapis|gemini|deepseek|x\.ai|grok)/i, key: "errors.providerNotFound" },
  { test: /timeout|timed out/i, key: "errors.timeout" },
  { test: /network|connection|econnrefused|failed to fetch/i, key: "errors.networkError" },
  { test: /insufficient_quota|quota|billing/i, key: "errors.providerQuota" },
  { test: /500|internal server error/i, key: "errors.serverError" },
  { test: /invalid_argument|bad request|\b400\b/i, key: "errors.providerBadRequest" },
];

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
 * @param fallbackKey translation used when nothing more specific matches (default: the generic message)
 */
export function humanizeError(error, lang = "en", fallbackKey = "errors.generic") {
  const rawMessage = typeof error === "string" ? error : error?.message;
  const status = typeof error === "object" && error !== null ? error.status : undefined;

  if (!rawMessage) return translate(fallbackKey, lang);

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

  const statusKey = keyFromStatus(status);
  if (statusKey) return translate(statusKey, lang);

  return translate(fallbackKey, lang);
}

export default humanizeError;
