/** "What's new": newest first. `id` must grow with every release (it drives the "new" badge). */

export const CHANGELOG = [
  {
    id: 4, date: "2026-10-09",
    items: {
      en: ["A fairer public track record: every forecast counts once and stays counted, hit rates come with a 95% range, and \"accuracy\" is now shown as the average price error",
        "Confidence now means the chance that the predicted direction is right",
        "Stronger account security: 2FA recovery codes, a password to change your email, security e-mails and a captcha instead of account lock-outs",
        "The simulator, P&L tracker, personal stats, AI consensus and the full scanner are now free for everyone",
        "Coin pages and market signals load much faster; a morning overview even without an AI key",
        "Clearer texts in every language: plural forms, units and number formats"],
      sk: ["Férovejšia verejná úspešnosť: každá predikcia sa započíta raz a už z nej nezmizne, úspešnosť smeru má 95 % interval a „presnosť“ sa ukazuje ako priemerná odchýlka ceny",
        "Istota teraz znamená pravdepodobnosť, že predikovaný smer vyjde",
        "Lepšie zabezpečenie účtu: záložné kódy 2FA, heslo pri zmene e-mailu, bezpečnostné e-maily a captcha namiesto zamykania účtu",
        "Simulátor, sledovanie zisku portfólia, osobné štatistiky, konsenzus AI a celý skener sú teraz pre všetkých zadarmo",
        "Stránky mincí a trhové signály sa načítajú oveľa rýchlejšie; ranný prehľad aj bez AI kľúča",
        "Jasnejšie texty vo všetkých jazykoch: správne tvary slov, jednotky a formát čísel"],
      cs: ["Férovější veřejná úspěšnost: každá predikce se započítá jednou a už z ní nezmizí, úspěšnost směru má 95% interval a „přesnost“ se ukazuje jako průměrná odchylka ceny",
        "Jistota nyní znamená pravděpodobnost, že předpovězený směr vyjde",
        "Lepší zabezpečení účtu: záložní kódy 2FA, heslo při změně e-mailu, bezpečnostní e-maily a captcha místo zamykání účtu",
        "Simulátor, sledování zisku portfolia, osobní statistiky, konsenzus AI a celý skener jsou nyní pro všechny zdarma",
        "Stránky mincí a tržní signály se načítají mnohem rychleji; ranní přehled i bez AI klíče",
        "Jasnější texty ve všech jazycích: správné tvary slov, jednotky a formát čísel"],
      de: ["Eine fairere öffentliche Erfolgsbilanz: Jede Prognose zählt einmal und bleibt gezählt, Trefferquoten haben einen 95-%-Bereich und „Genauigkeit“ wird als durchschnittliche Preisabweichung gezeigt",
        "Die Sicherheit gibt jetzt an, wie wahrscheinlich die vorhergesagte Richtung eintrifft",
        "Mehr Kontosicherheit: 2FA-Wiederherstellungscodes, Passwort zum Ändern der E-Mail, Sicherheits-E-Mails und ein Captcha statt Kontosperren",
        "Simulator, Portfolio-Gewinnverfolgung, persönliche Statistik, KI-Konsens und der volle Scanner sind jetzt für alle kostenlos",
        "Coin-Seiten und Marktsignale laden viel schneller; ein Morgenüberblick auch ohne KI-Schlüssel",
        "Klarere Texte in allen Sprachen: Pluralformen, Einheiten und Zahlenformate"],
      pl: ["Uczciwsza publiczna skuteczność: każda prognoza liczy się raz i już nie znika, skuteczność kierunku ma przedział 95%, a „dokładność” pokazujemy jako średnie odchylenie ceny",
        "Pewność oznacza teraz prawdopodobieństwo, że przewidywany kierunek się sprawdzi",
        "Lepsze zabezpieczenie konta: kody zapasowe 2FA, hasło przy zmianie e-maila, e-maile bezpieczeństwa i captcha zamiast blokady konta",
        "Symulator, śledzenie zysku portfela, osobiste statystyki, konsensus AI i pełny skaner są teraz darmowe dla wszystkich",
        "Strony monet i sygnały rynkowe ładują się znacznie szybciej; poranny przegląd nawet bez klucza AI",
        "Jaśniejsze teksty we wszystkich językach: formy liczby mnogiej, jednostki i format liczb"],
    },
  },
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
