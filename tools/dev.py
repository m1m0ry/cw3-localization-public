#!/usr/bin/env python3
"""CW3 maintainer entry: doctor, test, plan, build, apply, resume and status.

No publication, privilege escalation, security-setting changes or automatic rollback.
"""
from pathlib import Path
from contextlib import nullcontext
import argparse
import json
import os
import subprocess
import sys
import time
import tempfile
import zipfile

from dev_lock import desktop_lock
import dev_environment as environment
import dev_session as sessions
import player_install as player

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'local-only/dev.json'
DEFAULT_SESSION = ROOT / 'local-only/evidence/dev-session.json'


def read_config(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def classify(paths):
    paths = set(paths)
    if not paths:return 'none'
    if all(p.startswith(('docs/', 'tests/', 'tools/', '.github/')) or p in ('AGENTS.md', 'CONTRIBUTING.md', 'requirements-build.txt') for p in paths):
        return 'source'
    if all(p == 'src/rendering/CW3Rendering.cs' or p.startswith(('tests/', 'docs/')) for p in paths):
        return 'rendering'
    return 'package'


def changed_paths(base):
    tracked = subprocess.check_output(['git', 'diff', '--name-only', base], cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    return sorted(set(tracked + untracked))


def cloud_build(ref, version, target):
    import build_candidate
    return build_candidate.build(ref, version, target=target)


def build_options(command):
    command.add_argument('--local', action='store_true', help='Build clean local HEAD with existing verified inputs; no remote ref')
    command.add_argument('--build-config', type=Path, help='Local build input config (default: config.local.json)')
    command.add_argument('--output', type=Path, help='New local build work directory under local-only')


def check_build_options(args, parser):
    if args.local:
        if args.ref or not args.version:
            parser.error('Local builds require --version and no --ref; commit source locally, no push required')
        if getattr(args, 'python_only', False):
            parser.error('Local candidates require standalone C# tests; omit --python-only')
    elif args.build_config or args.output:
        parser.error('--build-config and --output require --local')
    elif not args.ref or not args.version:
        parser.error('Cloud builds require an already-pushed --ref and --version; no source is pushed automatically')


def build_selected(args, config):
    if args.local:
        import dev_local_build
        return dev_local_build.build(args.version, args.target, config, args.build_config, args.output)
    return cloud_build(args.ref, args.version, args.target)


def unpack_candidate(folder):
    info = player.read(folder / 'build-info.json')
    name = info['archive']
    if Path(name).name != name:raise ValueError('Invalid candidate archive name')
    archive = folder / name
    if player.digest(archive) != info['archive_sha256']:raise ValueError('Downloaded archive changed')
    destination = folder / 'unpacked'
    if destination.exists():raise ValueError('Candidate extraction already exists; use apply with that package')
    with tempfile.TemporaryDirectory(prefix='.unpack-', dir=folder) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            if any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n for n in names):
                raise ValueError('Archive path is unsafe')
            if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in source.infolist()):
                raise ValueError('Archive links are unsupported')
            source.extractall(stage)
        roots = list(stage.iterdir())
        if len(roots) != 1 or not roots[0].is_dir():raise ValueError('Expected one package root')
        package = roots[0]
        manifest = player.read(package / 'manifest.json')
        player.validate_manifest(manifest)
        for row in manifest['files']:
            if player.digest(player.safe(package, row['file'])) != row['after']:
                raise ValueError('Unpacked payload differs')
        package.rename(destination)
    return destination


def run_session(path, record, timeout):
    if sys.platform != 'darwin':raise RuntimeError('Desktop apply must run on the Mac, not the cloud executor')
    backend = sessions.NativeMac(record)
    def persist():sessions.save(path, record)
    try:
        with sessions.awake():sessions.advance(record, persist, backend, timeout)
        record.pop('blocked', None)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        record['blocked'] = dict(reason=str(error), time=time.time())
        persist()
        raise
    finally:persist()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--session', type=Path, default=DEFAULT_SESSION)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('doctor')
    test = commands.add_parser('test');test.add_argument('--python-only', action='store_true')
    plan = commands.add_parser('plan');plan.add_argument('--base', default='HEAD')
    build = commands.add_parser('build');build.add_argument('--kind', choices=('rendering','package'), required=True)
    build.add_argument('--ref');build.add_argument('--version')
    build.add_argument('--target', choices=('windows','macos'), default='macos')
    build_options(build)
    apply = commands.add_parser('apply');apply.add_argument('--package', type=Path, required=True)
    apply.add_argument('--timeout', type=float, default=20)
    resume = commands.add_parser('resume');resume.add_argument('--timeout', type=float, default=20)
    resume.add_argument('--retry-probe', action='store_true', help='Replace only this session’s unanswered read-only probe')
    commands.add_parser('status')
    run = commands.add_parser('run', help='Test, build the selected scope, install once, and smoke-test')
    run.add_argument('--kind', choices=('auto','source','rendering','package'), default='auto')
    run.add_argument('--base', default='HEAD')
    run.add_argument('--ref');run.add_argument('--version')
    run.add_argument('--target', choices=('windows','macos'), default='macos')
    build_options(run)
    run.add_argument('--timeout', type=float, default=20)
    run.add_argument('--python-only', action='store_true', help='Report C# suites as not run; intended for Python-only changes')
    args = parser.parse_args()
    selected = classify(changed_paths(args.base)) if args.action == 'run' and args.kind == 'auto' else getattr(args, 'kind', None)
    needs_lock = sys.platform == 'darwin' and (args.action in ('apply', 'resume') or (args.action == 'run' and selected not in ('source', 'none')))
    with desktop_lock() if needs_lock else nullcontext():
        execute(args, parser)


def execute(args, parser):
    config = read_config(args.config)
    if args.action == 'doctor':
        selected = environment.discover_python(config)
        print(json.dumps(dict(environment=selected, mono=environment.mono_config(config)), ensure_ascii=False, indent=2))
    elif args.action == 'test':
        result = environment.test_source(config, standalone=not args.python_only)
        sessions.save(ROOT / 'local-only/evidence/source-tests.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == 'plan':
        paths = changed_paths(args.base)
        print(json.dumps(dict(kind=classify(paths), files=paths,
                              note='Source-only changes need no game launch; rendering/package use an exact remote ref or explicit --local clean HEAD, then changed-only installation.'), indent=2))
    elif args.action == 'build':
        check_build_options(args, parser)
        output = build_selected(args, config)
        print('Built:', output)
    elif args.action == 'run':
        kind = classify(changed_paths(args.base)) if args.kind == 'auto' else args.kind
        if kind not in ('source', 'none') and args.session.exists() and player.read(args.session).get('phase') != 'verified':
            parser.error('Unfinished session: use resume instead of rebuilding/reinstalling')
        if kind == 'none':
            print('No changes detected; choose a kind explicitly to verify an already committed change')
            return
        if kind in ('rendering', 'package'):
            check_build_options(args, parser)
        if args.local and kind in ('rendering', 'package'):
            # The local builder pins HEAD before its single source gate, then checks
            # it again after compilation. Never reuse checks from an unpinned tree.
            downloaded = build_selected(args, config)
            checks = player.read(downloaded.parent / 'source-tests.json')
            sessions.save(ROOT / 'local-only/evidence/source-tests.json', checks)
        else:
            checks = environment.test_source(config, standalone=not args.python_only)
            sessions.save(ROOT / 'local-only/evidence/source-tests.json', checks)
            if kind == 'source':
                print(json.dumps(checks, indent=2));return
            downloaded = build_selected(args, config)
        if args.target != 'macos':
            print('Windows candidate verified:', downloaded, '; native Windows installation remains separate')
            return
        package = unpack_candidate(downloaded)
        record = sessions.new_session(config, package)
        record['source_tests'] = checks
        sessions.save(args.session, record)
        print(json.dumps(run_session(args.session, record, args.timeout), ensure_ascii=False, indent=2))
    elif args.action == 'status':
        print(json.dumps(player.read(args.session), ensure_ascii=False, indent=2))
    else:
        if args.timeout <= 0:parser.error('timeout must be positive')
        if args.action == 'apply':
            if args.session.exists():
                old = player.read(args.session)
                if old.get('phase') != 'verified':
                    parser.error('An unfinished session exists; use resume or a different --session')
            record = sessions.new_session(config, args.package)
            sessions.save(args.session, record)
        else:
            record = player.read(args.session)
            if args.retry_probe:
                sessions.retry_probe(record);sessions.save(args.session, record)
        result = run_session(args.session, record, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print('Smoke checks complete. Inspect the captured image; actual latency improvement is not measured here.')


if __name__ == '__main__':
    try:main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print('Not finished:', error, file=sys.stderr)
        sys.exit(1)
