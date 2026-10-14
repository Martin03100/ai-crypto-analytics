/** Frequently asked questions in every app language. `aPremium` replaces the answer while Premium mode is on. */

const F = [
  ["free", {
    en: "Is the app free?", sk: "Je aplikácia zadarmo?", cs: "Je aplikace zdarma?", de: "Ist die App kostenlos?", pl: "Czy aplikacja jest darmowa?",
  }, {
    en: "Yes. Every feature is free. You pay only your AI provider, and only if you connect your own key (Gemini has a free tier).",
    sk: "Áno. Všetky funkcie sú zadarmo. Platíš len svojmu AI poskytovateľovi, a to iba ak pripojíš vlastný kľúč (Gemini má bezplatnú úroveň).",
    cs: "Ano. Všechny funkce jsou zdarma. Platíš jen svému AI poskytovateli, a to pouze pokud připojíš vlastní klíč (Gemini má bezplatnou úroveň).",
    de: "Ja. Alle Funktionen sind kostenlos. Du zahlst nur deinen KI-Anbieter, und nur wenn du einen eigenen Schlüssel verbindest (Gemini hat ein Gratis-Kontingent).",
    pl: "Tak. Wszystkie funkcje są darmowe. Płacisz tylko swojemu dostawcy AI i tylko wtedy, gdy podłączysz własny klucz (Gemini ma darmowy limit).",
  }, {
    en: "The basic app is free, including forecasts from the free model and the public track record. Premium adds extra tools; the Premium page lists them and their price.",
    sk: "Základná aplikácia je zadarmo vrátane predikcií bezplatného modelu a verejného track recordu. Premium pridáva ďalšie nástroje; ich zoznam a cenu nájdeš na stránke Premium.",
    cs: "Základní aplikace je zdarma včetně predikcí bezplatného modelu a veřejného track recordu. Premium přidává další nástroje; jejich seznam a cenu najdeš na stránce Premium.",
    de: "Die Basis-App ist kostenlos, inklusive Prognosen des kostenlosen Modells und der öffentlichen Erfolgsbilanz. Premium bietet zusätzliche Werkzeuge; Liste und Preis stehen auf der Premium-Seite.",
    pl: "Podstawowa aplikacja jest darmowa, w tym prognozy darmowego modelu i publiczna historia trafień. Premium dodaje kolejne narzędzia; ich listę i cenę znajdziesz na stronie Premium.",
  }],
  ["apiKey", {
    en: "Do I need an AI API key?", sk: "Potrebujem API kľúč k AI?", cs: "Potřebuji API klíč k AI?", de: "Brauche ich einen KI-API-Schlüssel?", pl: "Czy potrzebuję klucza API do AI?",
  }, {
    en: "No. A free statistical model gives real forecasts right away. With your own key from Gemini, OpenAI, Anthropic, DeepSeek or xAI you can also compare the big AI models.",
    sk: "Nie. Bezplatný štatistický model dáva skutočné predikcie hneď. S vlastným kľúčom od Gemini, OpenAI, Anthropic, DeepSeek alebo xAI môžeš porovnávať aj veľké AI modely.",
    cs: "Ne. Bezplatný statistický model dává skutečné predikce hned. S vlastním klíčem od Gemini, OpenAI, Anthropic, DeepSeek nebo xAI můžeš porovnávat i velké AI modely.",
    de: "Nein. Ein kostenloses statistisches Modell liefert sofort echte Prognosen. Mit einem eigenen Schlüssel von Gemini, OpenAI, Anthropic, DeepSeek oder xAI kannst du auch die großen KI-Modelle vergleichen.",
    pl: "Nie. Darmowy model statystyczny od razu daje prawdziwe prognozy. Z własnym kluczem od Gemini, OpenAI, Anthropic, DeepSeek lub xAI możesz też porównywać duże modele AI.",
  }],
  ["advice", {
    en: "Is this investment advice?", sk: "Je to investičné poradenstvo?", cs: "Je to investiční poradenství?", de: "Ist das eine Anlageberatung?", pl: "Czy to porada inwestycyjna?",
  }, {
    en: "No. The app is an analytical tool: forecasts are estimates that are often wrong. It does not trade, hold money or execute orders. Every decision and its risk are yours.",
    sk: "Nie. Aplikácia je analytický nástroj: predikcie sú odhady, ktoré sa často mýlia. Neobchoduje, nedrží peniaze ani nevykonáva príkazy. Každé rozhodnutie a jeho riziko sú tvoje.",
    cs: "Ne. Aplikace je analytický nástroj: predikce jsou odhady, které se často mýlí. Neobchoduje, nedrží peníze ani neprovádí příkazy. Každé rozhodnutí a jeho riziko jsou tvoje.",
    de: "Nein. Die App ist ein Analysewerkzeug: Prognosen sind Schätzungen und liegen oft daneben. Sie handelt nicht, verwahrt kein Geld und führt keine Aufträge aus. Jede Entscheidung und ihr Risiko liegen bei dir.",
    pl: "Nie. Aplikacja jest narzędziem analitycznym: prognozy to szacunki, które często są błędne. Nie handluje, nie przechowuje pieniędzy ani nie wykonuje zleceń. Każda decyzja i jej ryzyko należą do ciebie.",
  }],
  ["accuracy", {
    en: "How accurate are the forecasts?", sk: "Aké presné sú predikcie?", cs: "Jak přesné jsou predikce?", de: "Wie genau sind die Prognosen?", pl: "Jak trafne są prognozy?",
  }, {
    en: "Every saved forecast is checked automatically when its horizon ends. The public track record shows how often each model got the direction right, its average price error and whether it beat a simple \"price stays the same\" guess. Until a model has at least 30 checked forecasts the numbers can be luck.",
    sk: "Každá uložená predikcia sa po skončení horizontu automaticky vyhodnotí. Verejný track record ukazuje, ako často model trafil smer, jeho priemernú chybu ceny a či porazil jednoduchý odhad „cena sa nezmení“. Kým model nemá aspoň 30 vyhodnotených predikcií, čísla môžu byť náhoda.",
    cs: "Každá uložená predikce se po skončení horizontu automaticky vyhodnotí. Veřejný track record ukazuje, jak často model trefil směr, jeho průměrnou chybu ceny a zda porazil jednoduchý odhad „cena se nezmění“. Dokud model nemá alespoň 30 vyhodnocených predikcí, čísla mohou být náhoda.",
    de: "Jede gespeicherte Prognose wird nach Ablauf ihres Horizonts automatisch geprüft. Die öffentliche Erfolgsbilanz zeigt, wie oft ein Modell die Richtung traf, seinen durchschnittlichen Preisfehler und ob es die einfache Annahme „der Kurs bleibt gleich“ schlug. Solange ein Modell weniger als 30 geprüfte Prognosen hat, können die Zahlen Zufall sein.",
    pl: "Każda zapisana prognoza jest automatycznie sprawdzana po upływie horyzontu. Publiczna historia trafień pokazuje, jak często model trafił kierunek, jego średni błąd ceny i czy pokonał proste założenie „cena się nie zmieni”. Dopóki model nie ma co najmniej 30 sprawdzonych prognoz, liczby mogą być przypadkiem.",
  }],
  ["wrong", {
    en: "Why is the AI sometimes completely wrong?", sk: "Prečo sa AI niekedy úplne mýli?", cs: "Proč se AI někdy úplně mýlí?", de: "Warum liegt die KI manchmal völlig daneben?", pl: "Dlaczego AI czasem całkowicie się myli?",
  }, {
    en: "Crypto prices react to news, large trades and moods that no model can foresee. An AI only weighs the data available at that moment. That is why the app measures every forecast publicly instead of promising results.",
    sk: "Ceny kryptomien reagujú na správy, veľké obchody a nálady, ktoré žiadny model nepredvída. AI len váži dáta dostupné v danej chvíli. Preto aplikácia každú predikciu verejne meria namiesto sľubovania výsledkov.",
    cs: "Ceny kryptoměn reagují na zprávy, velké obchody a nálady, které žádný model nepředvídá. AI jen váží data dostupná v danou chvíli. Proto aplikace každou predikci veřejně měří místo slibování výsledků.",
    de: "Kryptokurse reagieren auf Nachrichten, große Trades und Stimmungen, die kein Modell vorhersieht. Eine KI wägt nur die Daten ab, die im Moment verfügbar sind. Deshalb misst die App jede Prognose öffentlich, statt Ergebnisse zu versprechen.",
    pl: "Ceny kryptowalut reagują na wiadomości, duże transakcje i nastroje, których żaden model nie przewidzi. AI waży tylko dane dostępne w danej chwili. Dlatego aplikacja publicznie mierzy każdą prognozę zamiast obiecywać wyniki.",
  }],
  ["integrity", {
    en: "Can the track record be faked?", sk: "Dá sa track record zmanipulovať?", cs: "Dá se track record zmanipulovat?", de: "Kann die Erfolgsbilanz geschönt werden?", pl: "Czy historię trafień da się zmanipulować?",
  }, {
    en: "Not easily. A forecast can be saved only once and only within 15 minutes of being made, so nobody can wait and keep only the good ones. Deleting a forecast removes it from your history, but its result stays in the anonymous statistics.",
    sk: "Ľahko nie. Predikcia sa dá uložiť len raz a len do 15 minút od vytvorenia, takže nikto nemôže počkať a nechať si len tie dobré. Zmazanie predikcie ju odstráni z tvojej histórie, no jej výsledok ostane v anonymnej štatistike.",
    cs: "Snadno ne. Predikce jde uložit jen jednou a jen do 15 minut od vytvoření, takže nikdo nemůže počkat a nechat si jen ty dobré. Smazání predikce ji odstraní z tvé historie, ale její výsledek zůstane v anonymní statistice.",
    de: "Nicht so einfach. Eine Prognose lässt sich nur einmal und nur innerhalb von 15 Minuten speichern, niemand kann also abwarten und nur die guten behalten. Löschen entfernt sie aus deinem Verlauf, ihr Ergebnis bleibt aber in der anonymen Statistik.",
    pl: "Niełatwo. Prognozę można zapisać tylko raz i tylko w ciągu 15 minut od jej utworzenia, więc nikt nie może poczekać i zachować tylko dobrych. Usunięcie prognozy usuwa ją z twojej historii, ale jej wynik zostaje w anonimowych statystykach.",
  }],
  ["keySafety", {
    en: "Is my API key safe?", sk: "Je môj API kľúč v bezpečí?", cs: "Je můj API klíč v bezpečí?", de: "Ist mein API-Schlüssel sicher?", pl: "Czy mój klucz API jest bezpieczny?",
  }, {
    en: "It is encrypted with a key unique to your account before it is stored, never shown again in full and only sent to the provider it belongs to. You can delete it in Settings at any time.",
    sk: "Pred uložením sa zašifruje kľúčom jedinečným pre tvoj účet, už nikdy sa nezobrazí celý a posiela sa len poskytovateľovi, ku ktorému patrí. V Nastaveniach ho môžeš kedykoľvek zmazať.",
    cs: "Před uložením se zašifruje klíčem jedinečným pro tvůj účet, už nikdy se nezobrazí celý a posílá se jen poskytovateli, ke kterému patří. V Nastavení ho můžeš kdykoli smazat.",
    de: "Er wird vor dem Speichern mit einem nur für dein Konto geltenden Schlüssel verschlüsselt, nie wieder vollständig angezeigt und nur an den zugehörigen Anbieter gesendet. In den Einstellungen kannst du ihn jederzeit löschen.",
    pl: "Przed zapisaniem jest szyfrowany kluczem unikalnym dla twojego konta, nigdy więcej nie jest pokazywany w całości i trafia tylko do dostawcy, do którego należy. W Ustawieniach możesz go w każdej chwili usunąć.",
  }],
  ["data", {
    en: "What data do you keep and how do I delete my account?", sk: "Aké dáta uchovávate a ako zmažem účet?", cs: "Jaká data uchováváte a jak smažu účet?", de: "Welche Daten speichert ihr und wie lösche ich mein Konto?", pl: "Jakie dane przechowujecie i jak usunąć konto?",
  }, {
    en: "Only what the app needs: your account, saved forecasts and settings. Settings let you download all of it as one file or delete the account, which removes your data right away. Details are in the privacy policy.",
    sk: "Len to, čo aplikácia potrebuje: tvoj účet, uložené predikcie a nastavenia. V Nastaveniach si všetko stiahneš ako jeden súbor alebo zmažeš účet, čím sa tvoje dáta hneď odstránia. Podrobnosti sú v zásadách ochrany osobných údajov.",
    cs: "Jen to, co aplikace potřebuje: tvůj účet, uložené predikce a nastavení. V Nastavení si vše stáhneš jako jeden soubor nebo smažeš účet, čímž se tvá data hned odstraní. Podrobnosti jsou v zásadách ochrany osobních údajů.",
    de: "Nur was die App braucht: dein Konto, gespeicherte Prognosen und Einstellungen. In den Einstellungen lädst du alles als eine Datei herunter oder löschst das Konto, wodurch deine Daten sofort entfernt werden. Details stehen in der Datenschutzerklärung.",
    pl: "Tylko to, czego aplikacja potrzebuje: twoje konto, zapisane prognozy i ustawienia. W Ustawieniach pobierzesz wszystko jako jeden plik albo usuniesz konto, co od razu usuwa twoje dane. Szczegóły są w polityce prywatności.",
  }],
  ["slow", {
    en: "Why does the first page load sometimes take long?", sk: "Prečo sa prvá stránka niekedy načítava dlho?", cs: "Proč se první stránka někdy načítá dlouho?", de: "Warum lädt die erste Seite manchmal lange?", pl: "Dlaczego pierwsza strona czasem długo się ładuje?",
  }, {
    en: "The server runs on a free plan that falls asleep after a quiet period. The first request wakes it up, which can take up to a minute; the app tells you when that happens. After that it is fast.",
    sk: "Server beží na bezplatnom pláne, ktorý po chvíli bez návštev zaspí. Prvá požiadavka ho prebudí, čo môže trvať až minútu; aplikácia ti to oznámi. Potom je už rýchla.",
    cs: "Server běží na bezplatném plánu, který po chvíli bez návštěv usne. První požadavek ho probudí, což může trvat až minutu; aplikace ti to oznámí. Pak je už rychlá.",
    de: "Der Server läuft in einem kostenlosen Tarif, der nach einer ruhigen Phase einschläft. Die erste Anfrage weckt ihn, was bis zu einer Minute dauern kann; die App sagt dir Bescheid. Danach ist sie schnell.",
    pl: "Serwer działa w darmowym planie, który usypia po okresie bez ruchu. Pierwsze zapytanie go budzi, co może potrwać do minuty; aplikacja o tym poinformuje. Potem działa szybko.",
  }],
  ["install", {
    en: "Can I install it on my phone?", sk: "Dá sa nainštalovať do mobilu?", cs: "Dá se nainstalovat do mobilu?", de: "Kann ich sie auf dem Handy installieren?", pl: "Czy mogę zainstalować ją na telefonie?",
  }, {
    en: "Yes. Open the site in your browser and choose \"Install app\" or \"Add to Home Screen\". It then opens like an app and shows your last data even offline.",
    sk: "Áno. Otvor stránku v prehliadači a zvoľ „Inštalovať aplikáciu“ alebo „Pridať na plochu“. Potom sa otvára ako aplikácia a ukáže posledné dáta aj bez internetu.",
    cs: "Ano. Otevři stránku v prohlížeči a zvol „Instalovat aplikaci“ nebo „Přidat na plochu“. Pak se otevírá jako aplikace a ukáže poslední data i bez internetu.",
    de: "Ja. Öffne die Seite im Browser und wähle „App installieren“ oder „Zum Home-Bildschirm“. Sie öffnet sich dann wie eine App und zeigt deine letzten Daten auch offline.",
    pl: "Tak. Otwórz stronę w przeglądarce i wybierz „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”. Wtedy otwiera się jak aplikacja i pokazuje ostatnie dane także offline.",
  }],
  ["coins", {
    en: "Which coins are supported?", sk: "Ktoré mince sú podporované?", cs: "Které mince jsou podporované?", de: "Welche Coins werden unterstützt?", pl: "Które monety są obsługiwane?",
  }, {
    en: "Forecasts, alerts and the scanner cover 20 major coins, including Bitcoin, Ethereum, Solana, XRP, TON, SUI and PEPE. The portfolio advisor can also look up other coins.",
    sk: "Predikcie, alarmy a skener pokrývajú 20 hlavných mincí vrátane Bitcoinu, Etherea, Solany, XRP, TON, SUI a PEPE. Poradca portfólia vie vyhľadať aj ďalšie mince.",
    cs: "Predikce, alarmy a skener pokrývají 20 hlavních mincí včetně Bitcoinu, Etherea, Solany, XRP, TON, SUI a PEPE. Poradce portfolia umí vyhledat i další mince.",
    de: "Prognosen, Alarme und der Scanner decken 20 große Coins ab, darunter Bitcoin, Ethereum, Solana, XRP, TON, SUI und PEPE. Der Portfolio-Berater findet auch weitere Coins.",
    pl: "Prognozy, alerty i skaner obejmują 20 głównych monet, w tym Bitcoin, Ethereum, Solanę, XRP, TON, SUI i PEPE. Doradca portfela potrafi wyszukać też inne monety.",
  }],
  ["report", {
    en: "How do I report a bug or a security problem?", sk: "Ako nahlásim chybu alebo bezpečnostný problém?", cs: "Jak nahlásím chybu nebo bezpečnostní problém?", de: "Wie melde ich einen Fehler oder ein Sicherheitsproblem?", pl: "Jak zgłosić błąd lub problem z bezpieczeństwem?",
  }, {
    en: "Use the feedback button in the app for bugs and ideas. Security issues please report privately by e-mail; the security page explains how.",
    sk: "Chyby a nápady pošli cez tlačidlo spätnej väzby v aplikácii. Bezpečnostné problémy prosím nahlás súkromne e-mailom; postup je na stránke o bezpečnosti.",
    cs: "Chyby a nápady pošli přes tlačítko zpětné vazby v aplikaci. Bezpečnostní problémy prosím nahlas soukromě e-mailem; postup je na stránce o bezpečnosti.",
    de: "Fehler und Ideen schickst du über den Feedback-Button in der App. Sicherheitsprobleme melde bitte vertraulich per E-Mail; die Sicherheitsseite erklärt wie.",
    pl: "Błędy i pomysły wyślij przyciskiem opinii w aplikacji. Problemy z bezpieczeństwem zgłoś prywatnie e-mailem; strona o bezpieczeństwie wyjaśnia jak.",
  }],
];

export const FAQ = F.map(([id, q, a, aPremium]) => ({ id, q, a, aPremium }));
