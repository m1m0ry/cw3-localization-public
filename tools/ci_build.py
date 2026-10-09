"""Build a pinned source checkout; never authenticate, install or publish."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO = 'm1m0ry/cw3-localization-public'


def plan(root, tag, commit, inputs_sha256):
    if not re.fullmatch(r'v\d+\.\d+(?:\.\d+)?', tag):
        raise ValueError('Expected a version tag such as v12.6')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a full lowercase source commit SHA')
    if not re.fullmatch(r'[0-9a-f]{64}', inputs_sha256):
        raise ValueError('Expected the locked input archive SHA256')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    if git('rev-parse', 'HEAD') != commit or git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Build requires the exact clean source commit')
    build = root / 'local-only/ci-build'
    release = root / 'local-only/ci-release'
    if build.exists() or release.exists():
        raise ValueError('Use a fresh checkout for every build')
    return dict(source_repo=SOURCE_REPO, source_commit=commit, source_dirty=False,
                build_inputs_sha256=inputs_sha256, version=tag)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--tag', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--inputs-sha256', required=True)
    p.add_argument('--check-plan', action='store_true', help='Validate checkout and print provenance without building')
    a = p.parse_args()
    provenance = plan(ROOT, a.tag, a.source_commit, a.inputs_sha256)
    if a.check_plan:
        print(json.dumps(provenance, indent=2))
        return
    def run(*args):
        subprocess.run([*map(str, args)], cwd=ROOT, check=True)
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    build = ROOT / 'local-only/ci-build'
    release = ROOT / 'local-only/ci-release'
    run(sys.executable, ROOT/'tools/independent.py', '--config', Path(a.config).resolve(),
        '--output', build, '--version', a.tag)
    manifest_path = build/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update({k: v for k, v in provenance.items() if k != 'version'})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    release.mkdir()
    package = release/f'CW3-Windows-{a.tag}'
    run(sys.executable, ROOT/'tools/package_player.py', '--config', build/'install-config.json', '--output', package)
    archive = Path(str(package)+'.zip')
    player = json.loads((package/'manifest.json').read_text())
    for key, value in provenance.items():
        if player.get(key) != value:
            raise ValueError('Player manifest lost provenance: '+key)
    with __import__('zipfile').ZipFile(archive) as z:
        for row in player['files']:
            data = z.read(package.name+'/'+row['file'])
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['after']:
                raise ValueError('ZIP payload mismatch: '+row['file'])
    (release/'SHA256SUMS.txt').write_text(digest(archive)+'  '+archive.name+'\n')
    (release/'build-info.json').write_text(json.dumps(dict(
        provenance, archive=archive.name, archive_sha256=digest(archive),
        manifest_sha256=digest(package/'manifest.json'),
        payload_sha256={r['file']: r['after'] for r in player['files']}), indent=2)+'\n')
    print('Prepared', a.tag, 'from', a.source_commit, '; build only, no publish or install')


if __name__ == '__main__':
    main()
