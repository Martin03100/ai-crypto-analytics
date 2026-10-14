"""Machine-readable codes for the error messages users can see.

Error texts stay Slovak in the code (that is what the logs show), but every response also carries a stable code,
e.g. {"detail": "Nespravne pouzivatelske meno alebo heslo.", "code": "invalidCredentials"}, and the app translates the
code (errors.<code> in each language). Rewording a message therefore cannot break its translation: the tests check
that every message in the source still has a code.
"""

from __future__ import annotations

import re
from typing import Optional

# (pattern, code, name of the number captured by the first group); the first match wins, so specific patterns
# come before general ones.
_PATTERNS = (
    (r"neplatn[eé] alebo expirovan[eé] prihl[aá]senie", "sessionExpired"),
    (r"pr[ií]li[sš] ve[lľ]a po[zž]iadaviek.*?o (\d+)s", "rateLimited", "seconds"),
    (r"doč?asne uzamknut[yý].*?o (\d+) min", "accountLocked", "minutes"),
    (r"nespr[aá]vne pou[zž][ií]vate[lľ]sk[eé] meno alebo heslo", "invalidCredentials"),
    (r"pou[zž][ií]vate[lľ]sk[eé] meno je u[zž] obsaden[eé]", "usernameTaken"),
    (r"tento email u[zž] pou[zž][ií]va in[yý] [uú][cč]et", "emailTaken"),
    (r"k[oó]d je nespr[aá]vny alebo expirovan[yý]", "invalidResetCode"),
    (r"zadaj platn[uú] emailov[uú] adresu", "invalidEmail"),
    (r"aktu[aá]lne heslo nie je spr[aá]vne", "wrongCurrentPassword"),
    (r"nezn[aá]my ai provider", "unknownProvider"),
    (r"ulo[zž]en[aá] anal[yý]za nebola n[aá]jden[aá]", "notFound"),
    (r"csrf token", "csrfInvalid"),
    (r"nasta?la neo[cč]ak[aá]van[aá] chyba na serveri", "serverError"),
    (r"portf[oó]lio je pr[aá]zdne", "emptyPortfolio"),
    (r"[zž]iadne titulky na anal[yý]zu", "noHeadlines"),
    (r"[zž]iadna spr[aá]va na odoslanie", "noChatMessage"),
    (r"neplatn[aá] hodnota hlasu", "invalidVote"),
    (r"api kluc je pr[aá]zdny", "emptyApiKey"),
    (r"kluc sa nepodarilo overit", "keyVerificationFailed"),
    (r"najprv si over email", "emailNotVerified"),
    (r"zadaj 6-miestny k[oó]d z overovacej aplik", "totpRequired"),
    (r"k[oó]d z overovacej aplik[aá]cie u[zž] bol pou[zž]it[yý]", "totpReused"),
    (r"nespr[aá]vny k[oó]d z overovacej aplik", "totpInvalid"),
    (r"overenie, [zž]e nie si robot", "captchaFailed"),
    (r"potvr[dď], [zž]e nie si robot", "captchaRequired"),
    (r"[uú][cč]et administr[aá]tora sa ned[aá] zmaza[tť]", "adminCannotDelete"),
    (r"2fa u[zž] m[aá][sš] zapnut|najprv spusti nastavenie 2fa", "totpSetupState"),
    (r"na uk[aá][zž]kov[eé] d[aá]ta sa tipova[tť] ned[aá]", "tipMock"),
    (r"tipova[tť] sa d[aá] len do 2 hod[ií]n|[cč]as na tip pre t[uú]to predikciu u[zž] uplynul", "tipWindowClosed"),
    (r"predikcia je star[sš]ia ako 15 min[uú]t", "forecastTooOld"),
    (r"t[aá]to predikcia u[zž] je ulo[zž]en[aá]", "forecastAlreadySaved"),
    (r"na t[uú]to predikciu si u[zž] tipoval", "tipAlreadyExists"),
    (r"vlastn[eé]ho providera|vlastn[yý] provider (nie je spr[aá]vne|vr[aá]til presmerovanie)", "customProviderInvalid"),
    (r"pr[aá]zdn[uú] odpove[dď]|nepodarilo na[jĵ]?[sš]t [zž]iadny json|naparsovan[yý] json|chyba pri parsovan[ií] json|ch[yý]baj[uú]ce k[lľ][uú][cč]e|pol(e|ia) '[^']+'.*(mus[ií]|smie)|ai vr[aá]tila \d+ bodov|odpor[uú][cč]anie \d+|sektor '[^']+' nem[aá]", "aiInvalidResponse"),
    (r"najprv ulo[zž] api kl[uú][cč] pre tohto providera", "noKeyToTest"),
    (r"pou[zž][ií]vate[lľ]sk[eé] meno mus[ií] ma[tť] 3", "usernameInvalid"),
    (r"predikciu sa nepodarilo overi[tť]", "forecastUnverified"),
    (r"dosiahol si limit (\d+) ulo[zž]en[yý]ch", "savedLimit", "limit"),
    (r"t[aá]to funkcia je dostupn[aá] v premium", "premiumOnly"),
    (r"m[oô][zž]e[sš] ma[tť] najviac (\d+) akt[ií]vnych alarmov", "alertLimit", "max"),
    (r"pred platbou potvr[dď] podmienky", "checkoutConsent"),
    (r"t[aá]to minca nie je podporovan[aá]", "coinUnsupported"),
    (r"t[aá]to funkcia je moment[aá]lne vypnut[aá]", "featureOff"),
    (r"hodnota alarmu je mimo povolen[eé]ho rozsahu", "alertRange"),
    (r"stripe k[lľ][uú][cč] je neplatn[yý]", "stripeKeyInvalid"),
    (r"vlo[zž] tajn[yý] k[lľ][uú][cč] zo stripe", "stripeKeyFormat"),
    (r"stripe sa nepodarilo kontaktova[tť]", "stripeUnreachable"),
    (r"stripe odmietol po[zž]iadavku", "stripeRejected"),
    (r"zatia[lľ] nie je dos[tť] vyhodnoten[yý]ch predikci[ií]", "notEnoughData"),
    (r"poz[ií]cia nebola n[aá]jden[aá]", "positionNotFound"),
    (r"m[oô][zž]e[sš] sledova[tť] najviac (\d+) minc[ií]", "maxPositions", "n"),
    (r"tento [uú][cč]et je zablokovan[yý]", "accountBlocked"),
    (r"pr[ií]stup len pre administr[aá]tora", "adminOnly"),
    (r"prez[yý]vka mus[ií] ma[tť] 3", "nicknameInvalid"),
    (r"t[aá]to prez[yý]vka je u[zž] obsaden[aá]", "nicknameTaken"),
    (r"t[aá]to prez[yý]vka nie je povolen[aá]", "nicknameBlocked"),
    (r"prihl[aá]senie cez google nie je zapnut[eé]", "googleDisabled"),
    (r"prihl[aá]senie cez google sa nepodarilo", "googleFailed"),
    (r"[uú][cč]et s t[yý]mto e-mailom u[zž] existuje", "googleAccountExists"),
    (r"platby za premium zatia[lľ] nie s[uú] spusten[eé]", "billingOff"),
    (r"platobn[uú] br[aá]nu sa nepodarilo otvori[tť]", "billingFailed"),
    (r"m[oô][zž]e[sš] ma[tť] najviac (\d+) pl[aá]nov", "scheduleLimit", "max"),
    (r"podporuje len z[aá]kladn[eé] mince", "basicCoinsOnly"),
    (r"pl[aá]n predikcie nebol n[aá]jden[yý]", "scheduleNotFound"),
    (r"historick[eé] ceny sa teraz nepodarilo", "whatifUnavailable"),
    (r"na v[yý]po[cč]et je zatia[lľ] m[aá]lo", "whatifShort"),
    (r"nepodporovan[aá] minca alebo obdobie", "unsupportedCoinPeriod"),
    (r"t[aá]to udalos[tť] v kalend[aá]ri nie je", "eventMissing"),
    (r"najviac 50 pripomienok", "reminderLimit"),
    (r"tento prehliada[cč] nepodporuje upozornenia", "pushUnsupported"),
    (r"upozornenia v prehliada[cč]i e[sš]te nem[aá][sš]", "pushNotOn"),
    (r"tento profil neexistuje", "profileMissing"),
    (r"tento t[yý][zž]de[nň] u[zž] m[aá][sš] tip", "challengeAlready"),
    (r"tipy na tento t[yý][zž]de[nň] s[uú] u[zž] uzavret[eé]", "challengeClosed"),
    (r"tip je mimo rozumn[eé]ho rozsahu", "challengeRange"),
    (r"v[yý]zvu sa teraz nepodarilo na[cč][ií]ta[tť]", "challengeUnavailable"),
    (r"bezplatn[yý] model|chyba pri na[cč][ií]tan[ií] historick[yý]ch d[aá]t|nedostatok historick[yý]ch d[aá]t|trhov[eé] d[aá]ta moment[aá]lne|trhove data sa nepodarilo", "quantUnavailable"),
    (r"administr[aá]tor mus[ií] ma[tť] zapnut[eé] 2fa", "adminNeeds2fa"),
    (r"predplatn[eé] sa nepodarilo zru[sš]i[tť]", "subscriptionCancelFailed"),
    (r"pou[zž][ií]vate[lľ] nebol n[aá]jden[yý]", "userNotFound"),
    (r"administr[aá]tora nie je mo[zž]n[eé] zablokova[tť]", "adminCannotBlock"),
    (r"alarm nebol n[aá]jden[yý]", "alertNotFound"),
    (r"spr[aá]va sa nena[sš]la", "messageNotFound"),
    (r"backtest podporuje z[aá]kladn[eé] mince", "backtestUnsupported"),
    (r"uk[aá][zž]kov[eé] d[aá]ta sa nedaj[uú] zdie[lľ]a[tť]", "shareMock"),
    (r"demo predikcie sa nedaj[uú] zdie[lľ]a[tť]", "shareDemo"),
    (r"na t[uú]to predikciu sa tipova[tť] ned[aá]", "tipUnavailable"),
    (r"[uú]loha neexistuje alebo u[zž] vypr[sš]ala", "jobExpired"),
    (r"nepodporovan[aá] mena", "currencyUnsupported"),
    (r"neplatn[eé] id mince", "coinIdInvalid"),
    (r"nepodporovan[eé] obdobie grafu", "chartPeriodUnsupported"),
    (r"zdie[lľ]an[aá] predikcia neexistuje", "sharedNotFound"),
    (r"zadaj platn[uú] e-mailov[uú] adresu", "invalidEmail"),
    (r"odkaz na odhl[aá]senie je neplatn[yý]", "unsubscribeInvalid"),
    (r"pri t[yý][zž]dennom pl[aá]ne vyber de[nň]", "weekdayRequired"),
    (r"nezn[aá]me [cč]asov[eé] p[aá]smo", "timezoneUnknown"),
    (r"na konsenzus ch[yý]baj[uú] predikcie", "consensusNoForecasts"),
)
_COMPILED = tuple((re.compile(p[0], re.IGNORECASE), p[1], p[2] if len(p) > 2 else None) for p in _PATTERNS)
CODES = frozenset(p[1] for p in _PATTERNS)


def lookup(message: Optional[str]) -> Optional[tuple[str, dict]]:
    """(code, params) for a user-facing message, or None for an unknown one (e.g. a provider's own text)."""
    if not isinstance(message, str) or not message:
        return None
    for pattern, code, param in _COMPILED:
        match = pattern.search(message)
        if match:
            return code, ({param: match.group(1)} if param else {})
    return None
