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
  { test: /k[oó]d z overovacej aplik[aá]cie u[zž] bol pou[zž]it[yý]/i, key: "errors.totpReused" },
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
  { test: /dosiahol si limit (\d+) ulo[zž]en[yý]ch/i, key: "errors.savedLimit", params: (m) => ({ limit: m[1] }) },
  { test: /t[aá]to funkcia je dostupn[aá] v premium/i, key: "errors.premiumOnly" },
  { test: /m[oô][zž]e[sš] ma[tť] najviac (\d+) akt[ií]vnych alarmov/i, key: "errors.alertLimit", params: (m) => ({ max: m[1] }) },
  { test: /pred platbou potvr[dď] podmienky/i, key: "errors.checkoutConsent" },
  { test: /t[aá]to minca nie je podporovan[aá]/i, key: "errors.coinUnsupported" },
  { test: /t[aá]to funkcia je moment[aá]lne vypnut[aá]/i, key: "errors.featureOff" },
  { test: /hodnota alarmu je mimo povolen[eé]ho rozsahu/i, key: "errors.alertRange" },
  { test: /stripe k[lľ][uú][cč] je neplatn[yý]/i, key: "errors.stripeKeyInvalid" },
  { test: /vlo[zž] tajn[yý] k[lľ][uú][cč] zo stripe/i, key: "errors.stripeKeyFormat" },
  { test: /stripe sa nepodarilo kontaktova[tť]/i, key: "errors.stripeUnreachable" },
  { test: /stripe odmietol po[zž]iadavku/i, key: "errors.stripeRejected" },
  { test: /zatia[lľ] nie je dos[tť] vyhodnoten[yý]ch predikci[ií]/i, key: "errors.notEnoughData" },
  { test: /poz[ií]cia nebola n[aá]jden[aá]/i, key: "errors.positionNotFound" },
  { test: /m[oô][zž]e[sš] sledova[tť] najviac (\d+) minc[ií]/i, key: "errors.maxPositions", params: (m) => ({ n: m[1] }) },
  { test: /tento [uú][cč]et je zablokovan[yý]/i, key: "errors.accountBlocked" },
  { test: /pr[ií]stup len pre administr[aá]tora/i, key: "errors.adminOnly" },
  { test: /prez[yý]vka mus[ií] ma[tť] 3/i, key: "errors.nicknameInvalid" },
  { test: /t[aá]to prez[yý]vka je u[zž] obsaden[aá]/i, key: "errors.nicknameTaken" },
  { test: /platby za premium zatia[lľ] nie s[uú] spusten[eé]/i, key: "errors.billingOff" },
  { test: /platobn[uú] br[aá]nu sa nepodarilo otvori[tť]/i, key: "errors.billingFailed" },
  { test: /m[oô][zž]e[sš] ma[tť] najviac (\d+) pl[aá]nov/i, key: "errors.scheduleLimit", params: (m) => ({ max: m[1] }) },
  { test: /podporuje len z[aá]kladn[eé] mince/i, key: "errors.basicCoinsOnly" },
  { test: /pl[aá]n predikcie nebol n[aá]jden[yý]/i, key: "errors.scheduleNotFound" },
  { test: /historick[eé] ceny sa teraz nepodarilo/i, key: "errors.whatifUnavailable" },
  { test: /na v[yý]po[cč]et je zatia[lľ] m[aá]lo/i, key: "errors.whatifShort" },
  { test: /nepodporovan[aá] minca alebo obdobie/i, key: "errors.unsupportedCoinPeriod" },
  { test: /t[aá]to udalos[tť] v kalend[aá]ri nie je/i, key: "errors.eventMissing" },
  { test: /najviac 50 pripomienok/i, key: "errors.reminderLimit" },
  { test: /tento prehliada[cč] nepodporuje upozornenia/i, key: "errors.pushUnsupported" },
  { test: /upozornenia v prehliada[cč]i e[sš]te nem[aá][sš]/i, key: "errors.pushNotOn" },
  { test: /tento profil neexistuje/i, key: "errors.profileMissing" },
  { test: /tento t[yý][zž]de[nň] u[zž] m[aá][sš] tip/i, key: "errors.challengeAlready" },
  { test: /tipy na tento t[yý][zž]de[nň] s[uú] u[zž] uzavret[eé]/i, key: "errors.challengeClosed" },
  { test: /tip je mimo rozumn[eé]ho rozsahu/i, key: "errors.challengeRange" },
  { test: /v[yý]zvu sa teraz nepodarilo na[cč][ií]ta[tť]/i, key: "errors.challengeUnavailable" },
  { test: /bezplatn[yý] model|chyba pri na[cč][ií]tan[ií] historick[yý]ch d[aá]t|nedostatok historick[yý]ch d[aá]t|trhov[eé] d[aá]ta moment[aá]lne|trhove data sa nepodarilo/i, key: "errors.quantUnavailable" },
];

const TECHNICAL_PATTERNS = [
  { test: /per ?day|perday/i, key: "errors.providerDailyQuota" },
  { test: /(gemini|openai|anthropic|deepseek|grok|x\.ai)[\s\S]{0,40}(\b500\b|internal)/i, key: "errors.providerServerError" },
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
