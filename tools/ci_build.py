"""Build a pinned source checkout; never authenticate, install or publish."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from ci_inputs import TARGETS
from ci_source import SOURCE_REPO, validate_version, verify_checkout

ROOT = Path(__file__).resolve().parents[1]

def package_stem(target_id, tag, requested_target=None):
    validate_version(tag)
    for target, selected in TARGETS.items():
        if selected['target_id'] == target_id:
            # The private fallback invokes this CLI without --target and still
            # normalizes its Windows envelope. Retire this default with that workflow.
            if requested_target is None:
                return 'CW3-Windows-' + tag
            if requested_target != target:
                raise ValueError('Built platform differs from requested package target')
            return selected['prefix'] + '-' + tag
    raise ValueError('Unsupported package target')


def plan(root, tag, commit, inputs_sha256):
    validate_version(tag)
    if not re.fullmatch(r'[0-9a-f]{64}', inputs_sha256):
        raise ValueError('Expected the locked input archive SHA256')
    verify_checkout(root, commit)
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
    p.add_argument('--target', choices=TARGETS, help='Explicit platform for the public workflow package name')
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
    package = release/package_stem(manifest['target_id'], a.tag, a.target)
    run(sys.executable, ROOT/'tools/package_player.py', '--config', build/'install-config.json', '--output', package)
    archive = Path(str(package)+'.zip')
    player = json.loads((package/'manifest.json').read_text())
    run(sys.executable, ROOT/'tools/verify_package.py', '--config', build/'install-config.json',
        '--package', archive, '--inspect-only')
    archive_sha = digest(archive)
    (release/'SHA256SUMS.txt').write_text(archive_sha+'  '+archive.name+'\n')
    (release/'build-info.json').write_text(json.dumps(dict(
        provenance, target_id=player['target_id'], archive=archive.name, archive_sha256=archive_sha,
        manifest_sha256=digest(package/'manifest.json'),
        payload_sha256={r['file']: r['after'] for r in player['files']}), indent=2)+'\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('archive='+archive.name+'\n')
    print('Prepared', a.tag, 'from', a.source_commit, '; build only, no publish or install')


if __name__ == '__main__':
    main()
