"""Package an explicit source allowlist and the complete game runtime."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from game import VERSION


def source_files():
    names = '''app.py game.py lan.py lan_ui.py lan_discovery.py visuals.py
test_game.py test_lan.py test_release.py test_ui.py test_events.py test_platform.py
platform_paths.py run-linux.sh requirements-linux.txt
release_acceptance.py smoke_test.py lan_acceptance.py installer_art.py
simulate_balance.py benchmark_lan.py installer.iss
DopeWars-BFT-SPEC.md SPEC-STATUS.md RELEASE-NOTES.txt BALANCE-RESULTATER.txt
baseline-balance.json BALANCE-1.2.json LAN-YDELSE.json
version_info.txt build.ps1 requirements.txt logo.png bft.ico
LICENSE README.md BUILD.txt SIGNERING.txt LAES-MIG.txt LAN-LAES-MIG.txt
THIRD-PARTY.txt OMRAADER-KILDER.txt PRIVACY.txt CODE-SIGNING-POLICY.txt
.gitignore .gitattributes .github/workflows/windows.yml
ci/generate_brand.py ci/package_portable.py ci/verify-signed.ps1
signpath/artifact-configuration.xml'''.split()
    for name in names:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f'Missing required source: {name}')
        yield name, path
    for path in sorted((root / 'licenses').glob('*')):
        if path.is_file():
            yield path.relative_to(root).as_posix(), path


def stage():
    runtime = root / 'dist/DopeWars-BFT'
    if not (runtime / 'DopeWars-BFT.exe').is_file() or not (runtime / '_internal').is_dir():
        raise RuntimeError('Missing full onedir runtime')
    for name, path in source_files():
        dest = runtime / 'source' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    for name in ('LICENSE', 'LAES-MIG.txt', 'LAN-LAES-MIG.txt', 'THIRD-PARTY.txt',
                 'SIGNERING.txt', 'PRIVACY.txt', 'CODE-SIGNING-POLICY.txt', 'RELEASE-NOTES.txt'):
        shutil.copyfile(root / name, runtime / name)
    shutil.copytree(root / 'licenses', runtime / 'licenses', dirs_exist_ok=True)
    print(f'Staged runtime and {len(list(source_files()))} source files')


def archive(folder, label):
    folder = folder.resolve()
    if not (folder / 'DopeWars-BFT.exe').is_file() or not (folder / '_internal').is_dir():
        raise RuntimeError('Incomplete game folder')
    dest = root / 'dist' / (f'DopeWars-BFT-{VERSION}.zip' if label == 'unsigned' else f'DopeWars-BFT-{VERSION}-signed.zip')
    prefix = f'DopeWars-BFT-{VERSION}'
    dest.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    with ZipFile(dest, 'w', ZIP_DEFLATED, compresslevel=6) as z:
        for path in files:
            if path.is_symlink():
                raise RuntimeError(f'Symlink in distribution: {path.name}')
            z.write(path, f'{prefix}/{path.relative_to(folder).as_posix()}')
    with ZipFile(dest) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP integrity check failed')
        for path in files:
            if z.read(f'{prefix}/{path.relative_to(folder).as_posix()}') != path.read_bytes():
                raise RuntimeError(f'ZIP content changed: {path.name}')
    digest = hashlib.sha256(dest.read_bytes()).hexdigest().upper()
    dest.with_suffix('.sha256.txt').write_text(f'{digest}  {dest.name}\n', encoding='ascii')
    report = {'file': dest.name, 'sha256': digest, 'files': len(files), 'bytes': dest.stat().st_size,
              'zipIntegrity': True, 'label': label}
    (root / 'dist/reports').mkdir(exist_ok=True)
    (root / f'dist/reports/package-{label}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['stage', 'archive'])
    p.add_argument('--input', type=Path, default=root / 'dist/DopeWars-BFT')
    # This is a filename label. A signed release must run verify-signed.ps1 first.
    p.add_argument('--label', choices=['unsigned', 'signed'], default='unsigned')
    args = p.parse_args()
    if args.action == 'stage':
        stage()
    else:
        archive(args.input, args.label)
