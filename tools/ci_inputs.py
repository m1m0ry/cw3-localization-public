"""Fetch one fixed private release asset; verify every input before preparing CI."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile

from ci_source import authorize, verify_checkout

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'windows': dict(target_id='windows-steam-22453699', platform=5, prefix='CW3-Windows'),
    'macos': dict(target_id='macos-steam-22453699', platform=2, prefix='CW3-Mac'),
}


def lock(target, root=ROOT):
    if target not in TARGETS:
        raise ValueError('Unsupported build target')
    return json.loads((root / 'resources/ci-inputs.json').read_text())


def expected_hashes(root, target, metadata):
    profile = 'macos-target.json' if target == 'macos' else 'layout.json'
    originals = json.loads((root / 'resources' / profile).read_text())['original_hashes']
    font = json.loads((root / 'fonts/provenance.json').read_text())['external_full_sha256']
    return {**{'original/' + name: sha for name, sha in originals.items()},
            'font.ttf': font, **metadata['tools']}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def prepare(archive, root, commit, target, metadata):
    verify_checkout(root, commit)
    selected = metadata['targets'][target]
    if archive.stat().st_size != selected['bytes'] or digest(archive) != selected['sha256']:
        raise ValueError('CI archive size or SHA256 mismatch')
    expected = expected_hashes(root, target, metadata)
    local = root / 'local-only'
    outputs = [local / name for name in ('ci-inputs', 'independent-font', 'ci-config.json')]
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise ValueError('Use a fresh CI input workspace')
    local.mkdir(exist_ok=True)
    published = []
    with tempfile.TemporaryDirectory(prefix='ci-prepare-', dir=local) as folder:
        stage = Path(folder)
        inputs = stage / 'ci-inputs'
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if (len(entries) != len(expected) + 1 or
                    {entry.filename for entry in entries} != set(expected) | {'inputs.json'} or
                    any(entry.is_dir() or stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG)
                        for entry in entries)):
                raise ValueError('Unexpected or unsafe CI archive entries')
            rows = json.loads(source.read('inputs.json'))['files']
            if (not isinstance(rows, list) or len(rows) != len(expected) or
                    {row['file']: row['sha256'] for row in rows} != expected or
                    any(type(row['bytes']) is not int or row['bytes'] < 0 for row in rows)):
                raise ValueError('CI input manifest differs from public fingerprints')
            for row in rows:
                name = row['file']
                destination = inputs / name
                if not destination.resolve().is_relative_to(inputs.resolve()):
                    raise ValueError('Unsafe CI input path')
                entry = source.getinfo(name)
                if entry.file_size != row['bytes']:
                    raise ValueError('CI input size mismatch')
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as content, destination.open('wb') as output:
                    shutil.copyfileobj(content, output)
                if digest(destination) != row['sha256']:
                    raise ValueError('CI input fingerprint mismatch')
        font = stage / 'independent-font'
        font.mkdir()
        shutil.copyfile(inputs / 'font.ttf', font / 'font.ttf')
        out = local / 'ci-inputs'
        config = dict(target_id=TARGETS[target]['target_id'], original=str(out / 'original'),
                      game=str(out / 'original'), crossover='/unused', mono_version='wine-mono-10.4.1',
                      mono_runtime='/usr/bin/mono', mono_compiler=str(out / 'tools/mcs.exe'),
                      cecil=str(out / 'tools/Mono.Cecil.dll'))
        (stage / 'ci-config.json').write_text(json.dumps(config, indent=2) + '\n')
        try:
            for output in outputs:
                (stage / output.name).rename(output)
                published.append(output)
        except BaseException:
            for output in published:
                if output.is_dir():
                    shutil.rmtree(output)
                else:
                    output.unlink()
            raise
    print('Verified', len(expected), 'fixed inputs for', target)


def fetch(destination, target, metadata):
    # No public wheel or game/tool binary executes in this token-bearing process.
    if not os.environ.get('GH_TOKEN'):
        raise ValueError('Configure build-inputs / CW3_INPUTS_READ_TOKEN before building')
    repo = metadata['repository']
    if repo != 'm1m0ry/cw3-localization':
        raise ValueError('Unexpected private input repository')
    def api(endpoint):
        return json.loads(subprocess.check_output(['gh', 'api', '--hostname', 'github.com',
                                                  'repos/' + repo + endpoint], text=True))
    if api('')['private'] is not True:
        raise ValueError('Input repository must remain private')
    release = api('/releases/' + str(metadata['release_id']))
    selected = metadata['targets'][target]
    if (release.get('id') != metadata['release_id'] or release.get('draft') is not False or
            release.get('tag_name') != metadata['tag']):
        raise ValueError('Expected the published fixed input release')
    assets = [asset for asset in release['assets'] if asset['id'] == selected['asset_id']]
    if (len(assets) != 1 or assets[0].get('name') != selected['asset'] or
            assets[0].get('size') != selected['bytes'] or
            assets[0].get('digest') != 'sha256:' + selected['sha256'] or
            assets[0].get('state') != 'uploaded'):
        raise ValueError('Fixed input asset metadata mismatch')
    with destination.open('xb') as output:
        subprocess.run(['gh', 'api', '--hostname', 'github.com',
                        'repos/' + repo + '/releases/assets/' + str(selected['asset_id']),
                        '-H', 'Accept: application/octet-stream'], stdout=output, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    authorize(os.environ)
    verify_checkout(ROOT, args.source_commit)
    if args.source_commit != os.environ.get('GITHUB_SHA'):
        raise ValueError('Input request differs from the authorized workflow SHA')
    metadata = lock(args.target)
    with tempfile.TemporaryDirectory(prefix='cw3-inputs-') as folder:
        archive = Path(folder) / 'inputs.zip'
        fetch(archive, args.target, metadata)
        prepare(archive, ROOT, args.source_commit, args.target, metadata)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('sha256=' + metadata['targets'][args.target]['sha256'] + '\n')


if __name__ == '__main__':
    main()
