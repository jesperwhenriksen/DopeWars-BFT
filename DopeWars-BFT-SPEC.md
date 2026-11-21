# DopeWars-BFT – Kravspecifikation (LAN og spilbalance)

Repo: https://github.com/jesperwhenriksen/DopeWars-BFT · Basis: version 1.1.0, regelsæt `bft-5`, LAN-protokol `bft-lan-3` · Dato: 2026-11-21

## Instruktioner til agenten

- Arbejd spec-drevet: vælg ét krav-ID ad gangen, implementér det, skriv en test der refererer til ID'et, og opdatér status nederst.
- Læs den relevante kode, før du ændrer den. Alle "observationer" er læst i koden, men tal markeret *skal verificeres* er udledt og ikke målt. Bekræft dem med simulering, før konstanter ændres.
- Spørg udvikleren om de **åbne beslutninger** (sidste del), før du bygger noget, der afhænger af dem.
- Ændr ikke noget uden for kravets scope. Spillets tekster og dokumentation er på dansk.
- Commit-beskeder og tests henviser til krav-ID'et (fx `LAN-1.2`, `TIP-5`).

## 1. Formål og læsevejledning

Dokumentet samler de krav, der bygges videre på i LAN-delen og spilbalancen, så hver ændring kan udvikles og testes mod en fælles spec.

- **I scope:** LAN (`lan.py`, `lan_discovery.py`, `lan_ui.py`) og spilregler (`game.py`).
- **Uden for scope:** internetmatchmaking, global rangliste, fri chat, SignPath-signering.
- **Krav-ID:** `LAN-x.y` (netværk), `TIP-x` (politi-tip), `BAL-x` (balance og fairness), `NFR-x` (tværgående).
- **Prioritet:** MUST = skal med for at funktionen er færdig. SHOULD = bør med. COULD = kan udskydes.

## 2. Udgangspunkt (nuværende adfærd)

| Område | Nuværende adfærd | Kilde |
| --- | --- | --- |
| Transport | HTTPS med selvsigneret certifikat; fingerprint ligger i invitationen og tjekkes ved hvert kald. Ny forbindelse pr. kald. | `lan.py` `rpc()` |
| Polling | Klienten poller hvert 1 s; ved fejl fordobles intervallet op til 10 s. | `lan_ui.py` `Connection`, `failed()` |
| Discovery | UDP-broadcast på port 47653. Værten svarer kun, hvis lobbyen ikke er startet. | `lan_discovery.py` `Advertiser.run()` |
| Kapacitet | Maks. 8 spillere og 24 samtidige forbindelser. Serveren kører i samme proces som værtens UI. | `lan.py` `HTTP.slots` |
| Autoritet | Værten kører alle kommandoer. Kvitteringer (`request_id`) mod dobbeltkøb og `revision`-tjek mod forældet visning. | `lan.py` `Session.handle` |
| Tilfældighed | Hver spiller får eget seed ved start, så priser og hændelser er forskellige pr. spiller. | `lan.py` `op=='start'` |
| Offentlig visning | Dag, bank, aktiver, gæld, score og status. Historik fjernes fra visningen. | `lan.py` `Session.view` |
| Politi | Risiko = 0,18 + heat/500. Garanteret kontrol efter 6 dage uden. Flugt = 0,65 − 0,002 × fyldning i %. | `game.py` `advance()`, `do_police()` |

## 3. LAN-krav

### LAN-1 Automatisk genforbindelse efter start

Den manuelle procedure ved skiftet værts-IP (beskrevet i `LAN-LAES-MIG.txt`) skal ikke længere være nødvendig.

| ID | Krav | Prio |
| --- | --- | --- |
| LAN-1.1 | `Advertiser` svarer også på startede sessioner. Svaret har `started=true` og indeholder **ikke** `code`. | MUST |
| LAN-1.2 | Efter 3 fejlede polls i træk kører klienten `scan()` og matcher på `session`-id og `fingerprint`. | MUST |
| LAN-1.3 | Ved match opdateres og gemmes `invite` (vært og port) uden brugerhandling. Statuslinjen viser, at værten er fundet igen. | MUST |
| LAN-1.4 | Matcher fingerprint ikke, afvises svaret. En ny adresse accepteres aldrig på andet end session-id plus fingerprint. | MUST |
| LAN-1.5 | Manuel invitation bevares som reserve (ingen funktion fjernes). | MUST |

**Accept:** automatisk test i `test_lan.py`: start session, luk serveren, start den igen fra samme mappe på anden port. Klienten genforbinder uden input inden for 15 s. Fysisk test: skift Wi-Fi på værtens pc midt i en session.

### LAN-2 Aktivitetsstrøm

Giver følelsen af at spille sammen trods eget tempo.

| ID | Krav | Prio |
| --- | --- | --- |
| LAN-2.1 | Sessionen gemmer højst 50 offentlige hændelser `{id, tidspunkt, type, spiller-id, data}`. | MUST |
| LAN-2.2 | Hændelsestyper: spiller afsluttet (med score), spiller nået 25/50/75 % af forløbet, første virksomhed købt, opgivet (DNF). Tip-hændelser tilføjes af TIP-8. | SHOULD |
| LAN-2.3 | `view()` returnerer de seneste 20 med stigende id. Klienten viser nye hændelser i en liste på stillingssiden og kort i statuslinjen. | SHOULD |
| LAN-2.4 | Hændelser indeholder aldrig kontanter, varer, priser, by eller område. | MUST |
| LAN-2.5 | Faste reaktioner (5 emoji), maks. 1 pr. 5 s pr. spiller. | COULD |

**Accept:** test der opretter alle hændelsestyper og bekræfter, at en anden spillers `view` ikke indeholder private felter (`black`, `inventory`, `city`). Strømmen er ens for alle spillere.

### LAN-3 Effektiv polling

| ID | Krav | Prio |
| --- | --- | --- |
| LAN-3.1 | Klienten genbruger HTTPS-forbindelsen (keep-alive) og genopretter den kun ved fejl. | SHOULD |
| LAN-3.2 | `poll` kan sende `since={revision, lobby_version}`. Er intet ændret, svarer værten `{unchanged: true}` (under 200 bytes). | SHOULD |
| LAN-3.3 | Pollintervallet er stadig 1 s. Long-poll på op til 3 s er valgfri. | COULD |
| LAN-3.4 | Certifikat-fingerprint kontrolleres stadig ved hver (gen)forbindelse. | MUST |
| LAN-3.5 | Værtens UI-tråd blokeres ikke: p95-svartid for `poll` under 50 ms med 8 klienter. | SHOULD |

**Accept:** belastningstest i `test_lan.py` med 8 klienter i 60 s: ingen mistede kommandoer, og antal TLS-håndtryk pr. sekund er målt før og efter og noteret.

### LAN-4 Fælles marked (valgfri)

Se BAL-5. Prio: SHOULD.

### LAN-5 Stilling pr. dag

Se BAL-6. Prio: SHOULD.

## 4. Politi-tip (spiller mod spiller)

En spiller kan tippe politiet om en anden spiller, så vedkommende i 5 af sine egne spildage får flere politihændelser og sværere ved at løbe. Det er den første handling i LAN, hvor en spiller skader en anden, og det bryder derfor med lovningen i `LAN-LAES-MIG.txt` om, at andres hændelser ikke påvirker dig (se TIP-12).

**Balanceparametre (startværdier, kalibreres ved simulering):**

| Parameter | Startværdi | Begrundelse |
| --- | --- | --- |
| `TIP_DAYS` | 5 | Målets egne spildage, ikke tipperens eller uret. |
| `TIP_RISK_BONUS` | +0,20 | Risiko pr. dag 0,18 → 0,38 (plus heat). Med 6-dages-loftet stiger kontrolhyppigheden fra ca. 26 % til ca. 40 % pr. dag (*skal verificeres*). |
| `TIP_RUN_PENALTY` | −0,20, gulv 0,15 | Flugt i dag 45–65 %. Gulvet forhindrer sikker konfiskation. |
| `TIP_FIGHT_PENALTY` | 0 | Våben er en investering og skal ikke gøres værdiløse. |
| `TIP_COST` | 4 % af tipperens sorte kontanter, min. 500 kr. | Gratis tip giver dogpiling. |
| `TIP_COOLDOWN` | 10 af tipperens egne dage | Forhindrer, at én spiller holdes nede hele spillet. |

**Krav:**

| ID | Krav | Prio |
| --- | --- | --- |
| TIP-1 | Ny kommando `tip` med argument `target` (spiller-id) i `allowed` i `lan.py`. Kun i LAN, ikke i singleplayer. | MUST |
| TIP-2 | Afvises hvis: målet er en selv, er afsluttet eller opgivet, allerede har et aktivt tip, eller tipperen er i cooldown eller mangler penge. | MUST |
| TIP-3 | Værten sætter `tip_until_day = målets dag + TIP_DAYS` på målets tilstand og trækker `TIP_COST` fra tipperens sorte kontanter. | MUST |
| TIP-4 | I `advance()` lægges `TIP_RISK_BONUS` til risikoen, så længe `dag <= tip_until_day`. | MUST |
| TIP-5 | I `do_police()` falder flugtchancen med `TIP_RUN_PENALTY` (gulv 0,15). `explain` med green card er uberørt. | MUST |
| TIP-6 | Beskyttelse mod dødsspiral: under et tip kan helbredstab ved mislykket flugt højst koste halvdelen, eller tippet kan ikke føre til helbred 0. | SHOULD |
| TIP-7 | Målet får en dagshændelse ("Politiet har fået et tip") og ser "Tippet til dag N" i UI. Afsenderen er skjult. | MUST |
| TIP-8 | Offentlig hændelse i aktivitetsstrømmen (LAN-2): "Nogen har tippet politiet om <spiller>", uden afsender. | SHOULD |
| TIP-9 | Lobbyindstilling "Tillad tip" vælges af værten før start, gemmes i sessionen og vises for alle før de deltager. | MUST |
| TIP-10 | Determinisme: `tip` bruger ingen tilfældighed. Samme seed og kommandoer giver samme udfald. | MUST |
| TIP-11 | Gamle sessioner: manglende `tip_until_day` tolkes som 0. Migrering følger `upgrade_events()`-mønstret, og `check()` accepterer feltet. | MUST |
| TIP-12 | `LAN-LAES-MIG.txt`, `README.md` og lobbytekster opdateres (sætningen om, at andres hændelser ikke påvirker dig, ændres). | MUST |

**Accept:**

- Med fast seed er antal politikontroller over 10.000 simulerede dage højere med tip end uden. De målte tal noteres her.
- Flugtchance under tip er `max(0,15; normal − 0,20)`.
- Et andet tip på samme mål afvises. Samme `request_id` sendt to gange trækker kun én gang penge.
- Tip mod en offline spiller virker først, når vedkommendes dag går igen (dagtælleren står stille offline).
- En eksisterende session fra `bft-lan-3` kan stadig indlæses og spilles.

## 5. Mekanik-tweaks

Seks steder, hvor et lille tweak giver mere meningsfulde valg eller en mere retfærdig LAN-stilling. Alle tal er udledt af koden og skal bekræftes med en simulering (se NFR-6), før konstanterne ændres. Balanceændringer i `game.py` kræver nyt regelsæt (se NFR-1).

### BAL-1 Heat har næsten ingen effekt (SHOULD)

- **Observation:** risikoen er `0,18 + heat/500` (`game.py` `advance()`). Heat stiger kun med `antal/15` ved køb og `antal/20` ved salg og falder 5 pr. dag. Med frakkelommer (50) og rygsæk (100) giver en dags handel 5–11 heat, så heat sjældent når over ca. 30. Det er højst ca. 6 procentpoint ekstra risiko.
- **Forslag:** `heat/250` i stedet for `heat/500`, og UI viser dagens risiko i procent.
- **Accept:** simulering viser, at en strategi, der holder heat lav, får målbart færre kontroller end en, der ikke gør. UI viser risikoen.

### BAL-2 Pistol er dårligere end at løbe (SHOULD)

- **Observation:** flugt (`run`) lykkes med `0,65 − 0,2 × fyldning` (45–65 %). Pistol (`WEAPONS[1]`, 2.500 kr.) har 48 %, så den kun slår at løbe, når tasken er mere end 85 % fyldt. Hagl (67 %) og Riffel (82 %) er klart bedre.
- **Forslag:** hæv Pistol til ca. 0,58, eller lad våben give en bonus til `run`.
- **Accept:** for hver våbenklasse findes en fyldningsgrad, hvor den er det bedste valg (tabel genereret af test).

### BAL-3 Virksomheder vs. hvidvask i lange spil (SHOULD)

- **Observation:** `Billig` hvidvask koster 15 % (5–12 dage) og har ingen kapacitetsgrænse. Virksomhedernes gebyr er 20–25 %, og de tæller kun 60 % af prisen i score. I 180/365 dages spil er det svært at se, hvornår en virksomhed er det bedste valg. I 31 dage gør ventetiden på `Billig` den dyr.
- **Forslag (vælg ét):** (a) progressivt gebyr for hvidvask pr. dag over en grænse, (b) sænk virksomhedsgebyr, (c) hæv virksomheders daglige indkomst.
- **Accept:** simulering for 90, 180 og 365 dage: mindst én strategi med virksomheder slår ren `Billig`-hvidvask i median-score.

### BAL-4 Mules er næsten risikofri (COULD)

- **Observation:** `MULE_RISK = 0,001` pr. aktiv dag, uanset hvor meget en mule har på lager.
- **Forslag:** risikoen vokser med lageret (fx `0,001 + lager / 20.000`), så et stort lager er en afvejning.
- **Accept:** deterministisk test med fast seed: større lager giver højere tabssandsynlighed.

### BAL-5 Fælles marked i LAN (SHOULD)

- **Observation:** i `lan.py` (`op=='start'`) får hver spiller et eget seed. Priser og markedshændelser er derfor forskellige, og slutstillingen afhænger delvist af held.
- **Forslag:** lobbyindstilling "Samme marked for alle". Priser og markedshændelser trækkes fra en separat tilfældighedsstrøm, seedet af (session-seed, dag), så dag N har samme priser for alle. Politi, mules og hvidvask forbliver personlige.
- **Accept:** to spillere på samme dag ser samme priser. Gamle sessioner og singleplayer er uændrede (kun nyt regelsæt eller flag). Test for begge.

### BAL-6 Stilling pr. dag (SHOULD)

- **Observation:** spillerne er på forskellige dage, men stillingen sammenligner nuværende score. `game.py` gemmer allerede `{dag, score}` hver dag i `history`, men `Session.view()` tømmer den.
- **Forslag:** vis hver spillers `{dag, score}`-historik offentligt (kun de to felter) og lad stillingssiden have "Sammenlign ved dag N".
- **Accept:** en spiller på dag 10 kan sammenlignes med en anden spillers score ved dag 10. Test: ingen andre historikfelter (kontanter, varer, by) lækkes.

## 6. Tværgående krav

| ID | Krav | Prio |
| --- | --- | --- |
| NFR-1 | **Kompatibilitet:** ændrede LAN-beskeder hæver `PROTOCOL` (`bft-lan-4`). Ændrede spilregler hæver `RULESET` (`bft-6`). Migrering følger mønstret i `Session.__init__` (backup som `session.pre-v*.json`). Ældre klienter afvises med en klar besked. | MUST |
| NFR-2 | **Privatliv:** offentligt er kun dag, bank, aktiver, gæld, score, status og de eksplicit nummererede hændelser. Kontanter, varer, by og område forbliver private. | MUST |
| NFR-3 | **Determinisme:** samme seed og kommandosekvens giver samme tilstand. Nye funktioner ændrer ikke forbruget af tilfældighed i eksisterende forløb uden nyt regelsæt. | MUST |
| NFR-4 | **Serverautoritet:** alle nye kommandoer går gennem `Session.handle` med `request_id`-kvittering og `revision`-tjek. | MUST |
| NFR-5 | **Sikkerhed:** ingen nye åbne porte. Certifikat-pinning bevares. Discovery afslører aldrig join-koden for en startet session. | MUST |
| NFR-6 | **Tests:** hvert krav-ID har mindst én automatisk test i `test_lan.py`, `test_game.py` eller `test_events.py`. Balancekrav har desuden et simuleringsscript, som kan køres i `build.ps1`. Fysisk test med to pc'er og Windows Firewall forbliver en manuel tjekliste. | MUST |
| NFR-7 | **Dokumentation og sprog:** `LAN-LAES-MIG.txt`, `README.md` og tekster i spillet opdateres på dansk i samme ændring som funktionen. | MUST |
| NFR-8 | **Ydelse:** værtens UI forbliver responsivt med 8 spillere. Se LAN-3.5. | SHOULD |

## 7. Åbne beslutninger (spørg udvikleren)

| # | Spørgsmål | Anbefaling |
| --- | --- | --- |
| 1 | Skal "Tillad tip" være til eller fra som standard i nye lobbyer? | Fra. Værten vælger det aktivt, og alle ser det før de deltager. |
| 2 | Skal tipperen være anonym? | Ja. Målet advares, men ser ikke hvem. |
| 3 | Må et tip både øge risiko og sænke flugtchance? | Ja, men med pris, cooldown og gulv (TIP-2, TIP-5). Kalibrér ved simulering. |
| 4 | Skal "Samme marked for alle" (BAL-5) være til som standard? | Ja, fordi stillingen bliver mere retfærdig. Kan slås fra. |
| 5 | Skal balanceændringerne (BAL-1 til BAL-4) også gælde singleplayer? | Ja, samme regler i begge. Kræver `bft-6` og migrering af gamle saves. |
| 6 | Skal emoji-reaktioner (LAN-2.5) med i første runde? | Nej. Udskyd til aktivitetsstrømmen er afprøvet. |

## 8. Rækkefølge og status

Start med det, der er lille og ikke ændrer spilreglerne (LAN-1, LAN-5, LAN-3), og tag først derefter de funktioner, der kræver nyt regelsæt. Balanceopgaverne kommer efter, at simuleringen findes. Opdatér kolonnen Status (Åben / I gang / Til test / Færdig), når noget ændrer sig.

| Fase | Funktion | Krav-ID | Prio | Status |
| --- | --- | --- | --- | --- |
| 1 | Automatisk genforbindelse | LAN-1 | MUST | Til test |
| 1 | Stilling pr. dag | BAL-6 / LAN-5 | SHOULD | Til test |
| 1 | Effektiv polling | LAN-3 | SHOULD | Til test |
| 2 | Aktivitetsstrøm | LAN-2 | SHOULD | Til test |
| 2 | Simuleringsscript til balance | NFR-6 | MUST | Til test |
| 3 | Politi-tip | TIP-1 til TIP-12 | MUST | Til test |
| 3 | Fælles marked | BAL-5 / LAN-4 | SHOULD | Til test |
| 4 | Heat og pistol | BAL-1, BAL-2 | SHOULD | Til test |
| 4 | Virksomheder og hvidvask | BAL-3 | SHOULD | Til test |
| 4 | Mule-risiko | BAL-4 | COULD | Til test |

**Definition of done for hvert krav:**

- Koden opfylder kravets tekst, og alle MUST-rækker i dets tabel er opfyldt.
- Der er en automatisk test, der refererer til krav-ID'et.
- `build.ps1` kører grønt, inklusive pakkede acceptancetests.
- Dokumentation og tekster i spillet er opdateret (NFR-7).
- Fysisk test på to pc'er er afkrydset for LAN-funktioner.

## 9. Beslutninger og implementering 21. november 2026

Brugeren valgte alle anbefalinger. Version 1.2.0 er implementeret med
regelsæt bft-6 og protokol bft-lan-4. Automatisk validering, krav/test-kobling
og afgrænsninger står i SPEC-STATUS.md. LAN-rækkerne står fortsat Til test,
fordi den fysiske to-pc/Firewall-test endnu ikke er udført. Emoji (LAN-2.5)
er udskudt. Pollintervallet er fortsat ét sekund; long-poll er ikke indført.

Målt politi: 2.587/10.000 kontroldage uden tip mod 4.067 med tip. Ved heat
5 mod heat 60: 2.703 mod 4.428 kontroller med ny heat/250-regel.
Virksomhedsgebyrer er sænket til 12/11/10 % (valg b). Alle tre afprøvede
virksomhedsstrategier slår billig hvidvask i median ved 90, 180 og 365 dage.
Hele målegrundlaget ligger i baseline-balance.json, BALANCE-1.2.json og
BALANCE-RESULTATER.txt. BAL-2 sammenligner våben og flugt ved et givet budget.

LAN-belastning: 8 klienter, 60 sekunder pr. metode. p95 18,494 ms før mod
9,571 ms med keep-alive/since. TLS-håndtryk 6.694 mod 8. Begge forsøg
gennemførte 960 af 960 handlinger, uden dobbeltbetaling ved genafsendelse.
Se LAN-YDELSE.json for metode, pollingfrekvens og GUI-måling.
