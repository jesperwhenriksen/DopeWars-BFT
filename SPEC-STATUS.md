# Krav og validering – BFT 1.3.0

Version 1.3.0 samler disse spilændringer med Linux-understøttelsen fra PR #1.
`test_platform.py` kontrollerer datamapper, krypterede forbindelser og de
Linux-filer, der skal følge med distributionen. GitHub Actions har separate
Windows- og Linux-tests. Fysisk LAN på tværs af platformene afventer afprøvning.

Produktvalg: anonyme tip fra som standard, risiko og flugt påvirkes, fælles
marked til som standard, balance i begge spiltyper, emoji-reaktioner udskudt.

## Implementering og automatiske tests

- LAN-1.1 og NFR-5: `test_LAN_1_1_discovery_join_and_hide_started_code`.
- LAN-1.2–1.5 og LAN-3.3: `test_LAN_1_2_3_4_5_LAN_3_3_automatic_client_relocation_under_15s`.
  Ægte UDP, TLS, Qt-klient og DPAPI. Genstart fra samme mappe på en ny port.
  Fingerprint/session/ugyldig adresse afvises i NFR-5-matchtesten.
- LAN-2.1–2.4: alle hændelsestyper, grænser 50/20 og privatliv i
  `test_LAN_2_1_2_3_4_public_event_types_limits_and_privacy`. UI-listen testes også.
- LAN-2.5: udskudt efter brugerens valg; ingen knapper eller protokol til emoji.
- LAN-3.1, LAN-3.4: rigtig TLS-genbrug og pin-kontrol før payload.
- LAN-3.2: små unchanged-svar, andre spilleres ændringer, offline-status,
  genstart og genoprettet GUI-forbindelsesstatus testes.
- LAN-3.5 / NFR-8: kort 8-klient regressionstest plus 60 sekunder før/efter
  i `benchmark_lan.py`; resultat i LAN-YDELSE.json og BALANCE-RESULTATER.txt.
- LAN-4 / BAL-5: identiske tilsvarende markeder trods forskellige personlige
  tilfældighedsstrømme, egne dage, ruter og hvidvaskning. Fravalg testes også.
- LAN-5 / BAL-6: offentlig historik har kun dag/score; Qt sammenligner ved dag
  10, viser ikke-nåede spillere uden placering og bevarer valgt dag.
- TIP-1–TIP-3: LAN-only, validering, pris, begge spillerrevisioner og modtagers tid.
- TIP-4: præcis udløbsdag og offline måls egne dage; 10.000-dages risikomåling.
- TIP-5: flugtgrænser, våbenchance og green card testes på begge sider af udfaldsgrænsen.
- TIP-6: halv skade ved mislykket flugt og mindst ét helbred.
- TIP-7: privat advarsel, synlig tid og ingen gentagelse af allerede læst markedshændelse.
- TIP-8: offentlig hændelse uden afsender, kontanter, priser eller steder.
- TIP-9: gemte regler, standarder, discovery før deltagelse og manuel forhåndsvisning.
- TIP-10: ingen forbrug af spiller-RNG; deterministiske entity-id'er og kommandoer.
- TIP-11 / NFR-1: 1.1-session og gemt spil migreres med backup, priser,
  beholdninger, ordrer og RNG bevaret. Gamle klienter får tydelig versionsfejl.
  Allerede kvitteret køb fra gammel protokol kan genafsendes uden ny betaling.
- TIP-12 / NFR-7: danske regler i README, LAN-guide og lobby. Dokumentationskontrol i test_events.py.
- BAL-1–BAL-4: risikogrænser, våbenvalg, virksomheder og muletab i test_game.py.
  Reproducerbare større simulationer i simulate_balance.py med før/efter-resultater.
- NFR-2: eksplicit offentlig projektion; private markeder, seed og historie-felter filtreres.
- NFR-3: samme seed og handlinger giver samme tilstand; gamle RNG-tilstande bevares.
- NFR-4: tip går gennem kvitteringer og revisionskontrol. Dobbeltkommando,
  ændret payload og diskfejl testes; fejl ruller begge spilleres ændringer tilbage.
- NFR-6: kildetest, pakket EXE-test, komplette kilder og simulationsmuligheder i build.ps1.

Detaljerede testnavne og udfald står i dist/reports/source-tests.json og
packaged-release-self-test.json. NFR-7-dokumentationstesten læser de samme
medfølgende kildefiler fra den færdige pakke.

## Resterende fysisk afprøvning

LAN-kravene er **til fysisk accepttest**. Automatisk test på én Windows-pc
kan ikke afkrydse to pc'er, Wi-Fi-skift, router og Windows Firewall. Derfor
påstås specifikationens fulde Definition of done ikke opfyldt for LAN.
Følg tjeklisten i LAN-LAES-MIG.txt. Ingen ekstra porte, firewallændringer,
internetmatchmaking, chat eller signering indgår i denne ændring.

## Afgrænsninger

BAL-2 fortolkes som bedste valg med det våben, spilleren ejer eller har råd
til: pistol kan slå flugt, men slår ikke en allerede ejet riffel. Den højere
våbenklasse er stadig en opgradering. BAL-3 er en kontrolleret strategiprøve,
ikke et bevis på at en virksomhed altid giver gevinst i alle spil.
