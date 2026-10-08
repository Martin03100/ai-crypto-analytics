/** "What's new": newest first. `id` must grow with every release (it drives the "new" badge). */

export const CHANGELOG = [
  {
    id: 3, date: "2026-10-08",
    items: {
      en: ["Beginner view: one sentence and a traffic light per coin", "Browser notifications: alerts, \"AI changed its mind\", results and calendar reminders",
        "Event calendar: Fed, inflation, jobs report, option expiries, token unlocks and the Bitcoin halving",
        "\"What if\" calculator, public tipster profiles, accuracy over time and a weekly AI vs reality recap",
        "Search everything with Ctrl+K, market heatmap, quick view, glossary, CSV export and feedback", "German and Polish", "Faster first load and many small fixes"],
      sk: ["Jednoduchý režim: jedna veta a semafor pre každú mincu", "Upozornenia v prehliadači: alarmy, „AI zmenila názor“, výsledky a pripomienky z kalendára",
        "Kalendár udalostí: Fed, inflácia, trh práce, expirácie opcií, odomykanie tokenov a halving Bitcoinu",
        "Kalkulačka „Čo keby“, verejné profily tipérov, presnosť v čase a týždenný súhrn AI vs realita",
        "Hľadanie všetkého cez Ctrl+K, heatmapa trhu, rýchly prehľad, slovník pojmov, export do CSV a spätná väzba", "Nemčina a poľština", "Rýchlejšie načítanie a množstvo drobných opráv"],
      cs: ["Jednoduchý režim: jedna věta a semafor pro každou minci", "Upozornění v prohlížeči: alarmy, „AI změnila názor“, výsledky a připomínky z kalendáře",
        "Kalendář událostí: Fed, inflace, trh práce, expirace opcí, odemykání tokenů a halving Bitcoinu",
        "Kalkulačka „Co kdyby“, veřejné profily tipérů, přesnost v čase a týdenní souhrn AI vs realita",
        "Hledání všeho přes Ctrl+K, heatmapa trhu, rychlý přehled, slovník pojmů, export do CSV a zpětná vazba", "Němčina a polština", "Rychlejší načítání a spousta drobných oprav"],
      de: ["Einsteiger-Ansicht: ein Satz und eine Ampel pro Coin", "Browser-Benachrichtigungen: Alarme, „KI hat ihre Meinung geändert“, Ergebnisse und Kalender-Erinnerungen",
        "Ereigniskalender: Fed, Inflation, Arbeitsmarkt, Optionsverfall, Token-Unlocks und das Bitcoin-Halving",
        "„Was wäre wenn“-Rechner, öffentliche Tipper-Profile, Trefferquote im Zeitverlauf und ein wöchentlicher Rückblick KI vs. Realität",
        "Alles suchen mit Strg+K, Markt-Heatmap, Schnellansicht, Glossar, CSV-Export und Feedback", "Deutsch und Polnisch", "Schnellerer Start und viele kleine Verbesserungen"],
      pl: ["Widok dla początkujących: jedno zdanie i sygnalizator dla każdej monety", "Powiadomienia w przeglądarce: alerty, „AI zmieniła zdanie”, wyniki i przypomnienia z kalendarza",
        "Kalendarz wydarzeń: Fed, inflacja, rynek pracy, wygasanie opcji, odblokowania tokenów i halving Bitcoina",
        "Kalkulator „Co by było, gdyby”, publiczne profile typerów, skuteczność w czasie i cotygodniowe podsumowanie AI vs rzeczywistość",
        "Wyszukiwanie wszystkiego przez Ctrl+K, heatmapa rynku, szybki podgląd, słowniczek, eksport CSV i opinie", "Niemiecki i polski", "Szybsze ładowanie i wiele drobnych poprawek"],
    },
  },
  {
    id: 2, date: "2026-10-07",
    items: {
      en: ["Weekly \"Beat the AI\" challenge", "Is the confidence honest? Calibration and accuracy by market situation", "Share forecasts as Story and post images, invite QR code", "Coin pages for 20 coins", "Status page with 30-day history and a database backup for the admin"],
      sk: ["Týždenná výzva „Poraz AI“", "Je istota úprimná? Kalibrácia a presnosť podľa situácie na trhu", "Zdieľanie predikcií ako Story a príspevok, QR kód pozvánky", "Stránky pre 20 mincí", "Stránka stavu s 30-dňovou históriou a záloha databázy pre admina"],
      cs: ["Týdenní výzva „Poraz AI“", "Je jistota upřímná? Kalibrace a přesnost podle situace na trhu", "Sdílení predikcí jako Story a příspěvek, QR kód pozvánky", "Stránky pro 20 mincí", "Stránka stavu s 30denní historií a záloha databáze pro admina"],
      de: ["Wöchentliche Challenge „Schlag die KI“", "Ist die Zuversicht ehrlich? Kalibrierung und Trefferquote je Marktlage", "Prognosen als Story und Post teilen, Einladungs-QR-Code", "Seiten für 20 Coins", "Statusseite mit 30-Tage-Verlauf und Datenbank-Backup für den Admin"],
      pl: ["Cotygodniowe wyzwanie „Pokonaj AI”", "Czy pewność jest szczera? Kalibracja i skuteczność wg sytuacji rynkowej", "Udostępnianie prognoz jako Story i post, kod QR zaproszenia", "Strony dla 20 monet", "Strona statusu z 30-dniową historią i kopia bazy danych dla admina"],
    },
  },
  {
    id: 1, date: "2026-10-05",
    items: {
      en: ["Market signals from 30+ free sources, explained under every analysis", "Smart alerts: price, big moves, RSI and Fear & Greed"],
      sk: ["Trhové signály z 30+ bezplatných zdrojov, vysvetlené pod každou analýzou", "Inteligentné upozornenia: cena, veľké pohyby, RSI a Fear & Greed"],
      cs: ["Tržní signály z 30+ bezplatných zdrojů, vysvětlené pod každou analýzou", "Chytrá upozornění: cena, velké pohyby, RSI a Fear & Greed"],
      de: ["Marktsignale aus über 30 kostenlosen Quellen, unter jeder Analyse erklärt", "Smarte Alarme: Kurs, große Bewegungen, RSI und Fear & Greed"],
      pl: ["Sygnały rynkowe z ponad 30 darmowych źródeł, wyjaśnione pod każdą analizą", "Inteligentne alerty: cena, duże ruchy, RSI i Fear & Greed"],
    },
  },
];

const SEEN_KEY = "aca_changelog_seen";

export function latestId() {
  return CHANGELOG[0]?.id || 0;
}

export function hasUnreadChangelog() {
  try {
    return Number(localStorage.getItem(SEEN_KEY) || 0) < latestId();
  } catch {
    return false;
  }
}

export function markChangelogSeen() {
  try {
    localStorage.setItem(SEEN_KEY, String(latestId()));
  } catch {
    /* storage blocked */
  }
}

export function itemsFor(entry, lang) {
  return entry.items[lang] || entry.items.en;
}
