/** Plain-language glossary: term and a one-to-two sentence explanation in every app language. */

const G = [
  ["rsi", { en: "RSI", sk: "RSI", cs: "RSI", de: "RSI", pl: "RSI" }, {
    en: "Relative Strength Index (0–100). Above 70 the price has risen fast and may cool down; below 30 it has fallen fast and may bounce.",
    sk: "Index relatívnej sily (0–100). Nad 70 cena rýchlo rástla a môže sa ochladiť, pod 30 rýchlo padala a môže sa odraziť.",
    cs: "Index relativní síly (0–100). Nad 70 cena rychle rostla a může se ochladit, pod 30 rychle padala a může se odrazit.",
    de: "Relative-Stärke-Index (0–100). Über 70 ist der Kurs schnell gestiegen und kann abkühlen, unter 30 schnell gefallen und kann sich erholen.",
    pl: "Wskaźnik siły względnej (0–100). Powyżej 70 cena szybko rosła i może się ochłodzić, poniżej 30 szybko spadała i może odbić." }],
  ["macd", { en: "MACD", sk: "MACD", cs: "MACD", de: "MACD", pl: "MACD" }, {
    en: "Compares a fast and a slow moving average. When the fast one crosses above the slow one, momentum is turning up.",
    sk: "Porovnáva rýchly a pomalý kĺzavý priemer. Keď rýchly prekročí pomalý smerom nahor, dynamika sa otáča k rastu.",
    cs: "Porovnává rychlý a pomalý klouzavý průměr. Když rychlý překročí pomalý směrem nahoru, dynamika se otáčí k růstu.",
    de: "Vergleicht einen schnellen und einen langsamen gleitenden Durchschnitt. Kreuzt der schnelle den langsamen nach oben, dreht das Momentum nach oben.",
    pl: "Porównuje szybką i wolną średnią kroczącą. Gdy szybka przetnie wolną od dołu, dynamika zwraca się ku wzrostom." }],
  ["sma", { en: "Moving average (SMA)", sk: "Kĺzavý priemer (SMA)", cs: "Klouzavý průměr (SMA)", de: "Gleitender Durchschnitt (SMA)", pl: "Średnia krocząca (SMA)" }, {
    en: "The average price over the last N days. Price above its 50- or 200-day average is usually read as an uptrend.",
    sk: "Priemerná cena za posledných N dní. Cena nad 50- alebo 200-dňovým priemerom sa zvyčajne berie ako rastový trend.",
    cs: "Průměrná cena za posledních N dní. Cena nad 50- nebo 200denním průměrem se obvykle bere jako růstový trend.",
    de: "Der Durchschnittskurs der letzten N Tage. Ein Kurs über dem 50- oder 200-Tage-Schnitt gilt meist als Aufwärtstrend.",
    pl: "Średnia cena z ostatnich N dni. Cena powyżej średniej 50- lub 200-dniowej zwykle oznacza trend wzrostowy." }],
  ["fearGreed", { en: "Fear & Greed index", sk: "Index Fear & Greed", cs: "Index Fear & Greed", de: "Fear & Greed Index", pl: "Indeks Fear & Greed" }, {
    en: "Market mood from 0 (extreme fear) to 100 (extreme greed). Extremes often come before a turn, but not always.",
    sk: "Nálada trhu od 0 (extrémny strach) po 100 (extrémna chamtivosť). Extrémy často predchádzajú obratu, ale nie vždy.",
    cs: "Nálada trhu od 0 (extrémní strach) po 100 (extrémní chamtivost). Extrémy často předcházejí obratu, ale ne vždy.",
    de: "Marktstimmung von 0 (extreme Angst) bis 100 (extreme Gier). Extreme kommen oft vor einer Wende, aber nicht immer.",
    pl: "Nastrój rynku od 0 (skrajny strach) do 100 (skrajna chciwość). Skrajności często poprzedzają zwrot, ale nie zawsze." }],
  ["funding", { en: "Funding rate", sk: "Funding rate", cs: "Funding rate", de: "Funding Rate", pl: "Funding rate" }, {
    en: "A small fee between long and short traders on perpetual futures. High positive funding means many bets on a rise — a crowded trade.",
    sk: "Malý poplatok medzi long a short obchodníkmi na perpetual futures. Vysoký kladný funding znamená veľa stávok na rast — preplnený obchod.",
    cs: "Malý poplatek mezi long a short obchodníky na perpetual futures. Vysoký kladný funding znamená hodně sázek na růst — přeplněný obchod.",
    de: "Eine kleine Gebühr zwischen Long- und Short-Tradern bei Perpetual Futures. Hohe positive Funding Rate heißt: viele Wetten auf steigende Kurse.",
    pl: "Niewielka opłata między traderami long i short na kontraktach perpetual. Wysoki dodatni funding oznacza wiele zakładów na wzrost." }],
  ["openInterest", { en: "Open interest", sk: "Open interest", cs: "Open interest", de: "Open Interest", pl: "Open interest" }, {
    en: "The value of all open futures positions. Rising open interest with rising price means new money is joining the move.",
    sk: "Hodnota všetkých otvorených futures pozícií. Rastúci open interest spolu s cenou znamená, že do pohybu prichádzajú nové peniaze.",
    cs: "Hodnota všech otevřených futures pozic. Rostoucí open interest spolu s cenou znamená, že do pohybu přicházejí nové peníze.",
    de: "Der Wert aller offenen Futures-Positionen. Steigt er zusammen mit dem Kurs, fließt neues Geld in die Bewegung.",
    pl: "Wartość wszystkich otwartych pozycji futures. Rosnący open interest razem z ceną oznacza napływ nowych pieniędzy." }],
  ["liquidation", { en: "Liquidation", sk: "Likvidácia", cs: "Likvidace", de: "Liquidation", pl: "Likwidacja" }, {
    en: "A leveraged position closed by force because the trader's margin ran out. Waves of liquidations make moves sharper.",
    sk: "Páková pozícia nútene zatvorená, lebo obchodníkovi došla marža. Vlny likvidácií robia pohyby prudšími.",
    cs: "Páková pozice nuceně uzavřená, protože obchodníkovi došla marže. Vlny likvidací dělají pohyby prudšími.",
    de: "Eine gehebelte Position, die zwangsweise geschlossen wird, weil die Margin aufgebraucht ist. Liquidationswellen verstärken Bewegungen.",
    pl: "Pozycja z dźwignią zamknięta przymusowo, bo skończył się depozyt. Fale likwidacji wzmacniają ruchy cen." }],
  ["volatility", { en: "Volatility", sk: "Volatilita", cs: "Volatilita", de: "Volatilität", pl: "Zmienność" }, {
    en: "How much the price swings. The forecast range (the band around the line) widens when volatility is high.",
    sk: "Ako veľmi cena kolíše. Rozpätie prognózy (pás okolo čiary) sa pri vysokej volatilite rozširuje.",
    cs: "Jak moc cena kolísá. Rozpětí prognózy (pás kolem čáry) se při vysoké volatilitě rozšiřuje.",
    de: "Wie stark der Kurs schwankt. Die Prognose-Spanne (das Band um die Linie) wird bei hoher Volatilität breiter.",
    pl: "Jak mocno waha się cena. Przedział prognozy (pas wokół linii) poszerza się przy wysokiej zmienności." }],
  ["marketCap", { en: "Market cap", sk: "Trhová kapitalizácia", cs: "Tržní kapitalizace", de: "Marktkapitalisierung", pl: "Kapitalizacja rynkowa" }, {
    en: "Price × coins in circulation. It shows how big a project is better than the price of one coin.",
    sk: "Cena × počet mincí v obehu. Lepšie než cena jednej mince ukazuje, aký veľký projekt je.",
    cs: "Cena × počet mincí v oběhu. Lépe než cena jedné mince ukazuje, jak velký projekt je.",
    de: "Kurs × umlaufende Coins. Zeigt die Größe eines Projekts besser als der Preis eines einzelnen Coins.",
    pl: "Cena × liczba monet w obiegu. Lepiej niż cena jednej monety pokazuje, jak duży jest projekt." }],
  ["stablecoin", { en: "Stablecoin", sk: "Stablecoin", cs: "Stablecoin", de: "Stablecoin", pl: "Stablecoin" }, {
    en: "A coin pegged to the dollar (USDT, USDC). Growing stablecoin supply is money waiting on the sidelines to buy.",
    sk: "Minca naviazaná na dolár (USDT, USDC). Rastúca zásoba stablecoinov sú peniaze čakajúce na nákup.",
    cs: "Mince navázaná na dolar (USDT, USDC). Rostoucí zásoba stablecoinů jsou peníze čekající na nákup.",
    de: "Ein an den Dollar gekoppelter Coin (USDT, USDC). Wachsendes Stablecoin-Angebot ist Geld, das auf Käufe wartet.",
    pl: "Moneta powiązana z dolarem (USDT, USDC). Rosnąca podaż stablecoinów to pieniądze czekające na zakupy." }],
  ["etf", { en: "ETF flows", sk: "Toky do ETF", cs: "Toky do ETF", de: "ETF-Zuflüsse", pl: "Przepływy do ETF" }, {
    en: "Money going into or out of exchange-traded Bitcoin and Ether funds. Strong inflows mean big investors are buying.",
    sk: "Peniaze prichádzajúce do burzových fondov na Bitcoin a Ether alebo z nich. Silné prítoky znamenajú nákupy veľkých investorov.",
    cs: "Peníze přicházející do burzovních fondů na Bitcoin a Ether nebo z nich. Silné přítoky znamenají nákupy velkých investorů.",
    de: "Geld, das in börsengehandelte Bitcoin- und Ether-Fonds fließt oder abfließt. Starke Zuflüsse heißen: Großanleger kaufen.",
    pl: "Pieniądze wpływające do funduszy ETF na Bitcoina i Ether lub z nich wypływające. Silne napływy to zakupy dużych inwestorów." }],
  ["hashrate", { en: "Hashrate", sk: "Hashrate", cs: "Hashrate", de: "Hashrate", pl: "Hashrate" }, {
    en: "The computing power securing Bitcoin. A falling hashrate can mean miners are under pressure and selling.",
    sk: "Výpočtový výkon, ktorý zabezpečuje Bitcoin. Klesajúci hashrate môže znamenať, že ťažiari sú pod tlakom a predávajú.",
    cs: "Výpočetní výkon, který zabezpečuje Bitcoin. Klesající hashrate může znamenat, že těžaři jsou pod tlakem a prodávají.",
    de: "Die Rechenleistung, die Bitcoin absichert. Eine fallende Hashrate kann heißen, dass Miner unter Druck stehen und verkaufen.",
    pl: "Moc obliczeniowa zabezpieczająca Bitcoina. Spadający hashrate może oznaczać, że górnicy są pod presją i sprzedają." }],
  ["halving", { en: "Halving", sk: "Halving", cs: "Halving", de: "Halving", pl: "Halving" }, {
    en: "Every ~4 years the reward for mining a Bitcoin block is cut in half, so fewer new coins enter the market.",
    sk: "Približne každé 4 roky sa odmena za vyťaženie bloku Bitcoinu zníži na polovicu, takže na trh prichádza menej nových mincí.",
    cs: "Přibližně každé 4 roky se odměna za vytěžení bloku Bitcoinu sníží na polovinu, takže na trh přichází méně nových mincí.",
    de: "Etwa alle 4 Jahre halbiert sich die Belohnung für einen Bitcoin-Block, es kommen also weniger neue Coins auf den Markt.",
    pl: "Mniej więcej co 4 lata nagroda za wydobycie bloku Bitcoina spada o połowę, więc na rynek trafia mniej nowych monet." }],
  ["unlock", { en: "Token unlock", sk: "Odomknutie tokenov", cs: "Odemčení tokenů", de: "Token-Unlock", pl: "Odblokowanie tokenów" }, {
    en: "The day locked coins of the team or investors become sellable. Large unlocks can add selling pressure.",
    sk: "Deň, keď sa uzamknuté mince tímu alebo investorov dajú predať. Veľké odomknutia môžu zvýšiť tlak na predaj.",
    cs: "Den, kdy se uzamčené mince týmu nebo investorů dají prodat. Velká odemčení mohou zvýšit tlak na prodej.",
    de: "Der Tag, an dem gesperrte Coins des Teams oder von Investoren verkauft werden dürfen. Große Unlocks können Verkaufsdruck bringen.",
    pl: "Dzień, w którym zablokowane monety zespołu lub inwestorów można sprzedać. Duże odblokowania mogą zwiększyć presję sprzedaży." }],
  ["optionsExpiry", { en: "Options expiry", sk: "Expirácia opcií", cs: "Expirace opcí", de: "Optionsverfall", pl: "Wygaśnięcie opcji" }, {
    en: "The last Friday of each month crypto options settle (biggest at quarter end). Prices can be jumpy around it.",
    sk: "Posledný piatok v mesiaci sa vyrovnávajú krypto opcie (najväčšie na konci štvrťroka). Ceny okolo toho môžu skákať.",
    cs: "Poslední pátek v měsíci se vypořádávají krypto opce (největší na konci čtvrtletí). Ceny kolem toho mohou skákat.",
    de: "Am letzten Freitag im Monat verfallen Krypto-Optionen (am größten zum Quartalsende). Die Kurse können dann sprunghaft sein.",
    pl: "W ostatni piątek miesiąca rozliczają się opcje krypto (największe na koniec kwartału). Ceny mogą wtedy skakać." }],
  ["fomc", { en: "FOMC (Fed)", sk: "FOMC (Fed)", cs: "FOMC (Fed)", de: "FOMC (Fed)", pl: "FOMC (Fed)" }, {
    en: "The US central bank's rate decision. Lower rates usually help risky assets like crypto, higher rates hurt them.",
    sk: "Rozhodnutie americkej centrálnej banky o sadzbách. Nižšie sadzby zvyčajne pomáhajú rizikovým aktívam ako krypto, vyššie im škodia.",
    cs: "Rozhodnutí americké centrální banky o sazbách. Nižší sazby obvykle pomáhají rizikovým aktivům jako krypto, vyšší jim škodí.",
    de: "Der Zinsentscheid der US-Notenbank. Niedrigere Zinsen helfen meist riskanten Anlagen wie Krypto, höhere schaden ihnen.",
    pl: "Decyzja amerykańskiego banku centralnego w sprawie stóp. Niższe stopy zwykle pomagają ryzykownym aktywom jak krypto, wyższe szkodzą." }],
  ["cpi", { en: "CPI (inflation)", sk: "CPI (inflácia)", cs: "CPI (inflace)", de: "CPI (Inflation)", pl: "CPI (inflacja)" }, {
    en: "US consumer price data. Higher inflation than expected makes rate cuts less likely, which often weighs on crypto.",
    sk: "Údaje o spotrebiteľských cenách v USA. Vyššia inflácia, než sa čakalo, znižuje šancu na pokles sadzieb, čo krypto často brzdí.",
    cs: "Údaje o spotřebitelských cenách v USA. Vyšší inflace, než se čekalo, snižuje šanci na pokles sazeb, což krypto často brzdí.",
    de: "US-Verbraucherpreisdaten. Höhere Inflation als erwartet macht Zinssenkungen unwahrscheinlicher, was Krypto oft belastet.",
    pl: "Dane o cenach konsumpcyjnych w USA. Wyższa inflacja niż oczekiwano zmniejsza szansę na obniżki stóp, co często ciąży krypto." }],
  ["nfp", { en: "Jobs report (NFP)", sk: "Trh práce (NFP)", cs: "Trh práce (NFP)", de: "Arbeitsmarktbericht (NFP)", pl: "Raport z rynku pracy (NFP)" }, {
    en: "Monthly US employment numbers, usually the first Friday. Surprises move rate expectations and with them crypto.",
    sk: "Mesačné čísla o zamestnanosti v USA, zvyčajne prvý piatok. Prekvapenia menia očakávania sadzieb a s nimi aj krypto.",
    cs: "Měsíční čísla o zaměstnanosti v USA, obvykle první pátek. Překvapení mění očekávání sazeb a s nimi i krypto.",
    de: "Monatliche US-Beschäftigungszahlen, meist am ersten Freitag. Überraschungen verschieben Zinserwartungen und damit Krypto.",
    pl: "Miesięczne dane o zatrudnieniu w USA, zwykle w pierwszy piątek. Niespodzianki zmieniają oczekiwania co do stóp i krypto." }],
  ["bullish", { en: "Bullish / bearish", sk: "Býčí / medvedí", cs: "Býčí / medvědí", de: "Bullisch / bärisch", pl: "Byczy / niedźwiedzi" }, {
    en: "Bullish means expecting a rise, bearish means expecting a fall.",
    sk: "Býčí znamená očakávanie rastu, medvedí očakávanie poklesu.",
    cs: "Býčí znamená očekávání růstu, medvědí očekávání poklesu.",
    de: "Bullisch heißt steigende Kurse erwarten, bärisch fallende.",
    pl: "Byczy oznacza oczekiwanie wzrostu, niedźwiedzi — spadku." }],
  ["drawdown", { en: "Drawdown", sk: "Prepad (drawdown)", cs: "Propad (drawdown)", de: "Drawdown", pl: "Obsunięcie (drawdown)" }, {
    en: "The biggest drop from a peak to a later low. It shows how painful an investment could feel along the way.",
    sk: "Najväčší pokles z vrcholu na neskoršie dno. Ukazuje, aké bolestivé môže byť investovanie po ceste.",
    cs: "Největší pokles z vrcholu na pozdější dno. Ukazuje, jak bolestivé může být investování po cestě.",
    de: "Der größte Rückgang von einem Hoch zu einem späteren Tief. Zeigt, wie schmerzhaft eine Anlage zwischendurch sein kann.",
    pl: "Największy spadek od szczytu do późniejszego dołka. Pokazuje, jak bolesna może być inwestycja po drodze." }],
  ["accuracy", { en: "Accuracy %", sk: "Presnosť %", cs: "Přesnost %", de: "Genauigkeit %", pl: "Dokładność %" }, {
    en: "How close the forecast price was to the real one at the end of the horizon (100 % = exact).",
    sk: "Ako blízko bola predpovedaná cena k skutočnej na konci horizontu (100 % = presne).",
    cs: "Jak blízko byla předpovězená cena ke skutečné na konci horizontu (100 % = přesně).",
    de: "Wie nah der prognostizierte Kurs am Ende des Zeitraums am echten lag (100 % = exakt).",
    pl: "Jak blisko prognozowana cena była rzeczywistej na koniec horyzontu (100 % = dokładnie)." }],
  ["direction", { en: "Direction hit", sk: "Trafený smer", cs: "Trefený směr", de: "Richtung getroffen", pl: "Trafiony kierunek" }, {
    en: "Whether the forecast got up vs. down right. Above 50 % is better than a coin flip.",
    sk: "Či predpoveď trafila rast alebo pokles. Viac ako 50 % je lepšie než hod mincou.",
    cs: "Zda předpověď trefila růst nebo pokles. Více než 50 % je lepší než hod mincí.",
    de: "Ob die Prognose steigend vs. fallend richtig hatte. Über 50 % ist besser als ein Münzwurf.",
    pl: "Czy prognoza trafiła wzrost lub spadek. Powyżej 50 % to lepiej niż rzut monetą." }],
  ["naive", { en: "Naive guess", sk: "Naivný odhad", cs: "Naivní odhad", de: "Naive Schätzung", pl: "Naiwne założenie" }, {
    en: "Assuming the price stays where it is. A useful forecast has to beat this simple benchmark.",
    sk: "Predpoklad, že cena zostane tam, kde je. Užitočná predpoveď musí tento jednoduchý odhad poraziť.",
    cs: "Předpoklad, že cena zůstane tam, kde je. Užitečná předpověď musí tento jednoduchý odhad porazit.",
    de: "Die Annahme, dass der Kurs bleibt, wo er ist. Eine nützliche Prognose muss diesen einfachen Maßstab schlagen.",
    pl: "Założenie, że cena zostanie tam, gdzie jest. Użyteczna prognoza musi pokonać ten prosty punkt odniesienia." }],
  ["calibration", { en: "Calibration", sk: "Kalibrácia", cs: "Kalibrace", de: "Kalibrierung", pl: "Kalibracja" }, {
    en: "Whether a model that says \"80 % sure\" is right about 80 % of the time. Honest confidence is well calibrated.",
    sk: "Či model, ktorý tvrdí „istý na 80 %“, má pravdu zhruba v 80 % prípadov. Úprimná istota je dobre kalibrovaná.",
    cs: "Zda model, který tvrdí „jistý na 80 %“, má pravdu zhruba v 80 % případů. Upřímná jistota je dobře kalibrovaná.",
    de: "Ob ein Modell, das „zu 80 % sicher“ sagt, in etwa 80 % der Fälle recht hat. Ehrliche Zuversicht ist gut kalibriert.",
    pl: "Czy model, który mówi „pewny na 80 %”, ma rację w około 80 % przypadków. Szczera pewność jest dobrze skalibrowana." }],
  ["dca", { en: "DCA", sk: "DCA (pravidelné nákupy)", cs: "DCA (pravidelné nákupy)", de: "DCA (Sparplan)", pl: "DCA (regularne zakupy)" }, {
    en: "Buying a fixed amount at regular intervals instead of all at once, which smooths out the entry price.",
    sk: "Nákup pevnej sumy v pravidelných intervaloch namiesto všetkého naraz, čo vyrovnáva nákupnú cenu.",
    cs: "Nákup pevné částky v pravidelných intervalech místo všeho najednou, což vyrovnává nákupní cenu.",
    de: "Regelmäßig einen festen Betrag kaufen statt alles auf einmal – das glättet den Einstiegskurs.",
    pl: "Kupowanie stałej kwoty w regularnych odstępach zamiast wszystkiego naraz, co uśrednia cenę wejścia." }],
];

export const GLOSSARY = G.map(([id, term, def]) => ({ id, term, def }));

export function glossaryEntry(id) {
  return GLOSSARY.find((g) => g.id === id) || null;
}

export function localized(map, lang) {
  return map[lang] || map.en;
}
