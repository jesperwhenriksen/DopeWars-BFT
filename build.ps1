param([string]$PythonExe = '', [switch]$SkipDependencyInstall,
      [switch]$RunBalanceSimulation, [switch]$RunLanBenchmark, [string]$InnoCompiler = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe) {
    if (-not (Test-Path -LiteralPath '.build-env/Scripts/python.exe')) {
        & python -m venv .build-env
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 x64 first.' }
    }
    $PythonExe = Join-Path $PSScriptRoot '.build-env/Scripts/python.exe'
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
& $PythonExe -c 'import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize("P") == 8, "Python 3.12 x64 required"'
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python version/architecture.' }
if (-not $SkipDependencyInstall) {
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$env:QT_QPA_PLATFORM = 'offscreen'
& $PythonExe ci/generate_brand.py
if ($LASTEXITCODE -ne 0) { throw 'BFT artwork generation failed.' }
& $PythonExe app.py --release-self-test dist/reports/source-tests.json
if ($LASTEXITCODE -ne 0) { throw 'Source acceptance tests failed.' }
if ($RunBalanceSimulation) {
    & $PythonExe simulate_balance.py --output dist/reports/balance.json
    if ($LASTEXITCODE -ne 0) { throw 'Balancesimuleringen fejlede.' }
}
if ($RunLanBenchmark) {
    & $PythonExe benchmark_lan.py --seconds 60
    if ($LASTEXITCODE -ne 0) { throw 'LAN-belastningstesten fejlede.' }
}
& $PythonExe -m PyInstaller --noconfirm --clean --onedir --windowed --name DopeWars-BFT --icon bft.ico --version-file version_info.txt --add-data 'logo.png;.' app.py
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
& $PythonExe ci/package_portable.py stage
if ($LASTEXITCODE -ne 0) { throw 'Distribution staging failed.' }
foreach ($bftCheck in @('release-self-test', 'self-test')) {
    $bftReport = Join-Path $PSScriptRoot ('dist/reports/packaged-' + $bftCheck + '.json')
    $bftExe = Join-Path $PSScriptRoot 'dist/DopeWars-BFT/DopeWars-BFT.exe'
    $bftProcess = Start-Process -FilePath $bftExe -ArgumentList @('--' + $bftCheck, ('"' + $bftReport + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($bftProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $bftReport)) {
        if (Test-Path -LiteralPath $bftReport) {
            $bftFailed = Get-Content -LiteralPath $bftReport -Raw | ConvertFrom-Json
            Write-Host $bftFailed.details
        }
        throw "Packaged $bftCheck failed (exit $($bftProcess.ExitCode))."
    }
    $bftResult = Get-Content -LiteralPath $bftReport -Raw | ConvertFrom-Json
    if (-not $bftResult.passed) { throw "Packaged $bftCheck did not pass." }
}
& $PythonExe ci/package_portable.py archive --input dist/DopeWars-BFT --label unsigned
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
if ($InnoCompiler) {
    $InnoCompiler = (Resolve-Path -LiteralPath $InnoCompiler).Path
    & $PythonExe installer_art.py
    if ($LASTEXITCODE -ne 0) { throw 'Installergrafik kunne ikke oprettes.' }
    & $InnoCompiler installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installeren kunne ikke bygges.' }
    $bftVersion = & $PythonExe -c 'from game import VERSION; print(VERSION)'
    $bftInstaller = Join-Path $PSScriptRoot ('dist/DopeWars-BFT-Setup-' + $bftVersion + '.exe')
    $bftHash = (Get-FileHash -LiteralPath $bftInstaller -Algorithm SHA256).Hash
    ($bftHash + '  ' + [System.IO.Path]::GetFileName($bftInstaller)) | Set-Content -LiteralPath ($bftInstaller + '.sha256.txt') -Encoding ascii
}
Write-Host 'New version built and tested. Code signing still requires SignPath approval.'
