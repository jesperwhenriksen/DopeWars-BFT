; Offline per-user installer. Never delete the separate BFT-DopeWars save folder.
#ifndef BuildDir
  #define BuildDir "dist\DopeWars-BFT"
#endif
#ifndef PackageDir
  #define PackageDir "dist"
#endif
#define BftVersion "1.3.0"

[Setup]
AppId={{7A142A84-A49D-484C-9245-70792C11C1B2}
AppName=Dope Wars - BFT edition
AppVersion={#BftVersion}
AppPublisher=BFT
AppVerName=Dope Wars - BFT edition {#BftVersion}
DefaultDirName={localappdata}\Programs\BFT\DopeWars
DefaultGroupName=Dope Wars - BFT edition
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern dynamic
DisableWelcomePage=no
WizardImageFile=installer-assets\wizard.bmp
WizardSmallImageFile=installer-assets\wizard-small.bmp
WizardImageFileDynamicDark=installer-assets\wizard.bmp
WizardSmallImageFileDynamicDark=installer-assets\wizard-small.bmp
WizardImageStretch=yes
SetupIconFile=bft.ico
UninstallDisplayIcon={app}\DopeWars-BFT.exe
UninstallDisplayName=Dope Wars - BFT edition
OutputDir={#PackageDir}
OutputBaseFilename=DopeWars-BFT-Setup-{#BftVersion}
Compression=lzma2/normal
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupMutex=BFTDopeWarsSetup
VersionInfoVersion={#BftVersion}.0
VersionInfoProductName=Dope Wars - BFT edition
VersionInfoDescription=Dope Wars - BFT edition offline installation
#ifdef BftSigned
SignTool=BftSign
SignedUninstaller=yes
SignToolRetryCount=2
SignToolMinimumTimeBetween=1000
#endif

[Languages]
Name: "danish"; MessagesFile: "compiler:Languages\Danish.isl"

[LangOptions]
DialogFontName=Segoe UI
DialogFontSize=10
WelcomeFontName=Segoe UI
WelcomeFontSize=16

[Messages]
WelcomeLabel1=Velkommen til Dope Wars%nBFT edition
WelcomeLabel2=Byg din formue på tværs af otte danske byer. Spil alene, eller opret en LAN-lobby med vennerne.%n%nHele spillet er med i denne installation. Ingen konto, internetforbindelse eller ekstra downloads er nødvendige.%n%nGemte spil og highscores bevares ved opdatering og afinstallation.
FinishedLabel=Dope Wars - BFT edition er installeret.%n%nTil LAN: Alle starter spillet og vælger LAN. Én opretter en lobby, og de andre finder den automatisk på lokalnettet. Værten starter, når alle er klar.

[Tasks]
Name: "desktopicon"; Description: "Opret en genvej på skrivebordet"; GroupDescription: "Genveje:"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Dope Wars - BFT edition"; Filename: "{app}\DopeWars-BFT.exe"; WorkingDir: "{app}"
Name: "{group}\Spilguide"; Filename: "{app}\LAES-MIG.txt"
Name: "{group}\LAN med vennerne"; Filename: "{app}\LAN-LAES-MIG.txt"
Name: "{autodesktop}\Dope Wars - BFT edition"; Filename: "{app}\DopeWars-BFT.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\DopeWars-BFT.exe"; Description: "Start Dope Wars - BFT edition"; Flags: nowait postinstall skipifsilent
