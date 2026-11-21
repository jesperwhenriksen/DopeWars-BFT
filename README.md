# Dope Wars - BFT edition

A Danish-language Windows strategy game for singleplayer and local LAN play.
Start in Høje på Fyn, travel between eight Danish cities, and compete on public
highscores while each player advances at their own pace. All trading, police
events and money are fictional game mechanics.

This is an independent Python/Qt implementation. It does not include the
Beermat game's code, artwork or sounds, or the code of another Dope Wars project.

## Current status

The original BFT code and artwork in this source tree are licensed under MIT.
SignPath Foundation enrollment is in preparation and has not been completed.
Existing version 1.1.0 downloads are unsigned. A successful build or a passing
test does not mean that SignPath has approved or signed it.

## Play

Windows 10/11 x64. Extract the complete portable ZIP and start
`DopeWars-BFT.exe`. Keep `_internal` alongside it. No Python installation,
online account or Internet connection is required to play.

Choose singleplayer or LAN in the game. One player hosts a lobby; others find
it on the local network. The host starts the round. All players need the same
game version. See [the Danish guide](LAES-MIG.txt) and
[LAN instructions](LAN-LAES-MIG.txt).

Save games and scores are stored in `%LOCALAPPDATA%\BFT-DopeWars`.
Remove the extracted game folder to uninstall; saved data remains.

## Linux (fra kildekode)

Kræver Python 3.10+ og Qt-systembiblioteker (Arch/CachyOS: `qt6-base`, `xcb-util-cursor`).

```bash
./run-linux.sh          # opretter .venv-linux ved første kørsel og starter spillet
./run-linux.sh --test   # kører alle tests headless
```

Gemte spil og scores ligger i `~/.local/share/BFT-DopeWars` (eller `$XDG_DATA_HOME`,
eller `$BFT_DATA_DIR`). LAN-forbindelsesdata krypteres med en nøglefil (`linux-protect.key`,
rettigheder 0600) i samme mappe i stedet for Windows DPAPI. Åbn firewallen på privat net
for TCP 47652 og UDP 47653 (fx `sudo ufw allow 47652/tcp && sudo ufw allow 47653/udp`,
eller `firewall-cmd`). Linux og Windows kan spille LAN sammen, hvis versionen er den samme.

## Build and validation

Install Python 3.12 x64 and run `./build.ps1` in PowerShell. See [BUILD.txt](BUILD.txt).
The build uses pinned dependency versions, generates the original BFT branding,
runs source and packaged acceptance tests, and creates the full portable game.
The tests exercise game rules, Qt screens and real TLS connections on one PC.
They do not substitute for a physical multi-PC/firewall LAN test.

The [GitHub Actions workflow](.github/workflows/windows.yml) uses GitHub-hosted
Windows runners. Ordinary builds produce unsigned candidates. Signing can only
be requested manually on `main` after SignPath approves the project and the
maintainer configures its credentials and policy. No releases are published
automatically.

## Code signing policy

SignPath Foundation application in preparation; no sponsorship is claimed yet.
See [Code signing policy](CODE-SIGNING-POLICY.txt) and [signing setup](SIGNERING.txt).
The project maintainer is [@jesperwhenriksen](https://github.com/jesperwhenriksen).
The proposed production signing responsibilities are documented in the policy.

## Privacy

No advertising, analytics or telemetry. Network communication is initiated by
LAN hosting, discovery or joining a game. See [Privacy policy](PRIVACY.txt).

## License and artwork

The original BFT code and artwork are licensed under [MIT](LICENSE).
Dependencies retain their own licenses: [third-party notices](THIRD-PARTY.txt).
The BFT logo is generated from the project's original icon. The beer logo from
the private prototype is not part of this source tree or its builds.
