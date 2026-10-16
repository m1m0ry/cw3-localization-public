"""Dispatch a repository ref, wait for its exact Actions run, and verify the ZIP."""
from pathlib import Path
import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile

from ci_inputs import TARGETS
from ci_source import SOURCE_REPO, WORKFLOW, validate_ref_name, validate_version, verify_checkout
from package_player import PLAYER_SOURCES, supported_target
from verify_package import inspect_zip

ROOT = Path(__file__).resolve().parents[1]
GH_REPO = 'github.com/' + SOURCE_REPO
API_VERSION = '2026-03-10'


def api(endpoint, payload=None):
    command = ['gh', 'api', '--hostname', 'github.com', '-H', 'X-GitHub-Api-Version: ' + API_VERSION, endpoint]
    if payload is not None:
        command += ['--method', 'POST', '--input', '-']
    result = subprocess.run(command, input=None if payload is None else json.dumps(payload),
                            stdout=subprocess.PIPE, text=True, check=True)
    if payload is not None and not result.stdout.strip():
        raise ValueError('Dispatch returned no exact run ID; do not blindly dispatch again')
    return json.loads(result.stdout)


@contextmanager
def verification_source(commit):
    """Freeze trusted client source data before waiting; never execute fetched code."""
    names = set(PLAYER_SOURCES.values()) | {'player/使用说明-v12.txt',
            'resources/supported-build.json', 'resources/macos-target.json'}
    with tempfile.TemporaryDirectory(prefix='cw3-candidate-source-') as folder:
        snapshot = Path(folder)
        for name in names:
            # Match checkout filters, including the committed CRLF policy for .cmd.
            data = subprocess.check_output(['git', 'cat-file', '--filters', commit + ':' + name], cwd=ROOT)
            path = snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        yield snapshot


def verify_download(folder, commit, version, inputs_sha, target, source_root):
    selected = TARGETS[target]
    info = json.loads((folder / 'build-info.json').read_text())
    expected = dict(source_repo=SOURCE_REPO, source_commit=commit, source_dirty=False,
                    version=version, build_inputs_sha256=inputs_sha)
    if info.get('source_dirty') is not False or any(info.get(key) != value for key, value in expected.items()):
        raise ValueError('Downloaded candidate provenance differs from the requested build')
    if info.get('target_id') != selected['target_id']:
        raise ValueError('Downloaded candidate target differs from the requested build')
    name = selected['prefix'] + '-' + version + '.zip'
    if info.get('archive') != name or {p.name for p in folder.iterdir()} != {name, 'build-info.json', 'SHA256SUMS.txt'}:
        raise ValueError('Unexpected downloaded candidate files')
    if any(not p.is_file() or p.is_symlink() for p in folder.iterdir()):
        raise ValueError('Candidate contains a directory or link')
    digest = lambda data: hashlib.sha256(data).hexdigest()
    archive_sha = digest((folder / name).read_bytes())
    if info.get('archive_sha256') != archive_sha or (folder / 'SHA256SUMS.txt').read_text().strip() != archive_sha + '  ' + name:
        raise ValueError('Candidate ZIP SHA256 mismatch')
    with zipfile.ZipFile(folder / name) as archive:
        root = name.removesuffix('.zip')
        manifest_bytes = archive.read(root + '/manifest.json')
        manifest = json.loads(manifest_bytes)
        if digest(manifest_bytes) != info.get('manifest_sha256'):
            raise ValueError('Candidate manifest SHA256 mismatch')
        if manifest.get('source_dirty') is not False or manifest.get('format') != 2:
            raise ValueError('Candidate manifest is not a clean source build')
        if any(manifest.get(key) != selected[key] for key in ('target_id', 'platform')):
            raise ValueError('Candidate platform differs from selected target')
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise ValueError('Candidate manifest provenance mismatch: ' + key)
        supported = supported_target(manifest, source_root)
        # Reuse the package gate for paths, payload allowlist, hashes, installer
        # sources and instructions. It needs no original game input in this mode.
        build_manifest = dict(manifest, format=1, revision='independent-v12-candidate',
                              patch_version=version, version=supported['version'], steam_build=supported['steam_build'])
        inspected_root, _ = inspect_zip(archive, build_manifest, supported, None, source_root)
        if inspected_root != root:
            raise ValueError('Candidate package root differs from its archive name')
        hashes = {row['file']: row['after'] for row in manifest['files']}
        if hashes != info.get('payload_sha256'):
            raise ValueError('Candidate payload manifest mismatch')
        if archive.testzip() is not None:
            raise ValueError('Candidate ZIP CRC mismatch')
    return archive_sha


def check_run(run, run_id, ref, commit=None):
    if (run.get('id') != run_id or run.get('path') != WORKFLOW or run.get('head_branch') != ref
            or run.get('event') != 'workflow_dispatch' or
            run.get('repository', {}).get('full_name') != SOURCE_REPO or
            not re.fullmatch(r'[0-9a-f]{40}', run.get('head_sha', '')) or
            (commit is not None and run['head_sha'] != commit)):
        raise ValueError('Run differs from the requested repository ref or build workflow')
    return run['head_sha']


def build(ref, version, output=None, target='windows'):
    validate_ref_name(ref)
    validate_version(version)
    if target not in TARGETS:
        raise ValueError('Unsupported build target')
    if output is not None:
        output = Path(output).resolve()
        if not output.is_relative_to((ROOT / 'local-only').resolve()) or output.exists():
            raise ValueError('Choose a new output directory under local-only')
    client_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    verify_checkout(ROOT, client_commit)
    with verification_source(client_commit) as source_root:
        verify_checkout(ROOT, client_commit)
        return dispatch_and_verify(ref, version, output, target, client_commit, source_root)


def dispatch_and_verify(ref, version, output, target, client_commit, source_root):
    # The dispatch response owns the run identity; never select the latest run.
    response = api('repos/' + SOURCE_REPO + '/actions/workflows/build.yml/dispatches',
                   dict(ref=ref, inputs=dict(version=version, target=target)))
    run_id = response.get('workflow_run_id')
    if type(run_id) is not int or run_id <= 0:
        raise ValueError('Dispatch returned no exact run ID; do not blindly dispatch again')
    print('Run: https://github.com/' + SOURCE_REPO + '/actions/runs/' + str(run_id), flush=True)
    commit = check_run(api('repos/' + SOURCE_REPO + '/actions/runs/' + str(run_id)), run_id, ref)
    print('Pinned source:', ref, '->', commit, flush=True)
    if commit != client_commit:
        raise ValueError('Run source differs from this client. Use a clean checkout of ' + commit
                         + '; no candidate was downloaded. The printed run remains available.')
    subprocess.run(['gh', 'run', 'watch', str(run_id), '--repo', GH_REPO, '--exit-status', '--interval', '20'], check=True)
    run = api('repos/' + SOURCE_REPO + '/actions/runs/' + str(run_id))
    check_run(run, run_id, ref, commit)
    if run.get('conclusion') != 'success':
        raise ValueError('Build did not succeed')
    # Read input references at the run SHA, even if the selected ref has moved.
    lock_file = api('repos/' + SOURCE_REPO + '/contents/resources/ci-inputs.json?ref=' + commit)
    metadata = json.loads(base64.b64decode(lock_file['content'], validate=False))
    output = output or ROOT / 'local-only' / ('candidate-' + str(run_id))
    output.mkdir(parents=True, exist_ok=False)
    print('Download:', output, flush=True)
    try:
        subprocess.run(['gh', 'run', 'download', str(run_id), '--repo', GH_REPO,
                        '-n', 'cw3-package-' + commit + '-' + target, '-D', str(output)], check=True)
        sha = verify_download(output, commit, version, metadata['targets'][target]['sha256'], target, source_root)
    except BaseException:
        shutil.rmtree(output)
        raise
    print('PASS candidate:', output, '\nZIP SHA256:', sha, flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', required=True, help='Branch or tag in the fixed public repository; native dispatch ref')
    parser.add_argument('--version', required=True, help='Package version; creates no release or tag')
    parser.add_argument('--target', choices=TARGETS, default='windows')
    parser.add_argument('--output', help='New directory under local-only; default includes the exact run ID')
    args = parser.parse_args()
    try:
        build(args.ref, args.version, args.output, args.target)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, 'Candidate failed: ' + str(error) + '\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped waiting; the printed run URL remains available.\n')


if __name__ == '__main__':
    main()
