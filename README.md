# Dope Wars – BFT edition 1.3.0

Dansk strategispil til Windows og Linux med singleplayer og 2–8 venner på lokalnettet.
Start i Høje på Fyn, rejs mellem otte byer, og konkurrér på lovlig nettoformue.
Hver spiller styrer sit eget dagtempo. Handel, priser, politi og økonomi er
fiktive spilmekanikker. Køb og salg samme sted samme dag har ingen prisforskel.

Dette er en selvstændig Python/Qt-implementering. Beermats kode, billeder og
lyde indgår ikke. BFT-koden og projektets originale grafik er under MIT.

## Nyt i version 1.3.0

- Linux-understøttelsen fra PR #1 er med: datamapper, fonte og beskyttelse af
  gemte LAN-forbindelser. Windows bruger fortsat DPAPI.
- De seneste spil- og LAN-ændringer er samlet i samme version:

- Automatisk genforbindelse finder en startet vært på en ny adresse/port.
  Både session-id og det gemte certifikat skal matche. Reserveinvitationen bevares.
- Værten vælger **Samme marked for alle** (til som standard). Samme by,
  område og spildag har samme priser og prisbegivenheder. Politi, mules og
  ventetiden på bankens hvidvaskning er stadig personlige.
- **Tillad anonyme politi-tip** er fra som standard. Slår værten det til,
  kan andre spillere påvirke din kontrolrisiko og flugtchance. Alle ser
  indstillingen før tilslutning; den ændres ikke under spillet.
- Highscores viser fælles aktivitet og **Sammenlign ved dag N**. En spiller,
  der endnu ikke har nået dagen, får ingen placering ved den sammenligning.
- HTTPS-forbindelser genbruges. Uændrede polls har små svar; pin-kontrol
  udføres før data sendes på hver ny forbindelse.
- Heat betyder mere; pistol har 58 % kampchance. Virksomhedsgebyrer er
  12/11/10 %. Mules med større lager har højere risiko for tilbagefald.

Et tip koster 4 % af afsenderens sorte kontanter, oprundet, mindst 500 kr.
Det gælder til og med målets nuværende dag + 5, og afsenderen skal vente
10 egne spildage før et nyt tip. Offline spillere mister ingen dage.
Tip kan ikke stables. Kontrolrisikoen stiger 20 procentpoint, og flugtchancen
falder 20 procentpoint med gulv på 15 %. Kampchance og green cards er uændrede.
Mislykket flugt under tip giver halv skade, oprundet, og efterlader mindst
ét helbred. Afsenderen vises ikke til de andre spillere; værts-pc'en er betroet.

## Spil

Windows 10/11 x64. Brug installeren, eller udpak **hele** den portable ZIP og
start `DopeWars-BFT.exe`. Behold `_internal` ved siden af EXE-filen. Python,
internetkonto og internetforbindelse er ikke nødvendige for at spille.

Én vælger LAN og opretter en lobby. De andre finder den automatisk på samme
lokalnet. Alle markerer sig klar, og værten starter. Alle skal bruge 1.3.0.
Læs [spilguiden](LAES-MIG.txt) og [LAN-guiden](LAN-LAES-MIG.txt).

Gemte spil ligger i `%LOCALAPPDATA%\BFT-DopeWars` og bevares ved opdatering
og afinstallation. Gamle spil migreres til regelsæt `bft-6` / protokol
`bft-lan-4`, efter en sikkerhedskopi. Igangværende gamle LAN-sessioner beholder
personlige markeder og får politi-tip slået fra. Dagens priser, penge, ordrer
og tilfældighedstilstand bevares. Tidligere highscores holdes på eget regelsæt.

## Linux

Kræver Python 3.10+ og Qt-systembiblioteker. Pak kildekoden ud og kør:

```bash
bash run-linux.sh
bash run-linux.sh --test
```

Første kørsel opretter `.venv-linux` og henter Python-pakkerne; senere opdateres
de kun, hvis kravene er ændret. Derefter kan spillet køre uden internet.
På Ubuntu/Debian kræves bl.a. `python3-venv`, `libegl1`, `libgl1`,
`libxkbcommon-x11-0` og `libxcb-cursor0`; på Arch/CachyOS `qt6-base` og
`xcb-util-cursor`. Linux leveres som kildekode med startscript.

Data gemmes i `~/.local/share/BFT-DopeWars` eller under `$XDG_DATA_HOME`.
`BFT_DATA_DIR` kan angive en anden datamappe på begge platforme.
Linux beskytter LAN-forbindelser med AES-GCM og `linux-protect.key` med
rettigheder 0600. Bevar nøglen sammen med data, hvis de sikkerhedskopieres.
Windows og Linux bruger samme LAN-protokol. Værtens firewall skal tillade
TCP 47652 og UDP 47653 fra det private lokalnet. Fysisk LAN mellem platformene
skal stadig afprøves efter tjeklisten i LAN-guiden.

## Byg og test

Kør `./build.ps1` med Python 3.12 x64. [BUILD.txt](BUILD.txt) beskriver isoleret
miljø, installer, balancesimulering og 60-sekunders LAN-belastningstest.
Bygningen tester både kildekode og den pakkede EXE. [Specifikationen](DopeWars-BFT-SPEC.md)
og [testoversigten](SPEC-STATUS.md) kobler krav til tests og resterende afprøvning.
Resultater gemmes i `dist/reports`. Ingen spillergemninger bruges i testene.

Automatiske tests bruger ægte TLS og Qt på én Windows-pc. De erstatter ikke
den manuelle test med to fysiske pc'er, Wi-Fi-skift og Windows Firewall.
Den tjekliste står i LAN-guiden og er endnu ikke afkrydset.

[GitHub-workflowet](.github/workflows/windows.yml) tester Windows og Linux.
Windows-pakkerne bygges og testes fra samme kildekode. SignPath-ansøgningen
er indsendt, men godkendelse og signering er endnu ikke bekræftet.
Denne version er usigneret. Se [signeringspolitik](CODE-SIGNING-POLICY.txt)
og [opsætning](SIGNERING.txt).

## Privatliv og licens

Ingen reklamer, analyseværktøjer eller telemetri. LAN-stillingen deler dag,
bank, aktivværdi, gæld, score, status og historik med kun dag/score. Aktivitet
viser milepæle, afslutning, første virksomhed, DNF og anonyme tip. Kontanter,
varer, by, område og fremtidige markedsseeds sendes ikke til andre spillere.
Værten beregner og gemmer spillet. Se [privatliv](PRIVACY.txt).

[MIT-licens](LICENSE). Biblioteker beholder deres egne
[licenser](THIRD-PARTY.txt). Logo og ikoner er original BFT-grafik;
øl-logoet fra den private prototype indgår ikke i denne udgave.
