"""Build a complete candidate from a clean local HEAD and existing verified inputs."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

import dev_environment as environment
import game_target
from build_candidate import verify_download
from ci_inputs import TARGETS, digest
from ci_source import SOURCE_REPO, validate_version, verify_checkout
from dev_session import package_identity, save
from mono_tools import MonoTools

ROOT = Path(__file__).resolve().parents[1]


def clean_source(commit):
    verify_checkout(ROOT, commit)
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip():
        raise ValueError('Local build requires a clean HEAD, including untracked source; commit first (no push required)')


def input_identity(config, selected):
    target = game_target.load(config)
    original = environment.resolve_path(config['original'], ROOT)
    game_target.verify_inputs(original, target)
    font = ROOT / 'local-only/independent-font/font.ttf'
    font_sha = digest(font)
    if font_sha != json.loads((ROOT / 'fonts/provenance.json').read_text())['external_full_sha256']:
        raise ValueError('Prepare the verified full OFL font at local-only/independent-font/font.ttf')
    mono = MonoTools(config)
    # Paths and private configuration stay out of the portable candidate metadata.
    return dict(format=1, kind='local-file-inventory', target_id=target['target_id'],
                originals=target['original_hashes'], font_sha256=font_sha,
                tools={name: digest(path) for name, path in (
                    ('mono_runtime', mono.runtime), ('mono_compiler', mono.compiler), ('cecil', mono.cecil))},
                python={key: selected['details'][key] for key in ('version', 'packages')})


def build(version, target, dev_config, config_path=None, output=None):
    validate_version(version)
    if target not in TARGETS:
        raise ValueError('Unsupported local build target')
    path = environment.resolve_path(config_path or 'config.local.json', ROOT)
    if not path.is_file():
        raise ValueError('Local build requires an existing build config: ' + str(path))
    config = json.loads(path.read_text())
    if config.get('target_id') != TARGETS[target]['target_id']:
        raise ValueError('Build config target_id differs from --target')
    if not config.get('original'):
        raise ValueError('Local build config must name verified original inputs; no installed-game fallback')
    # Reuse the development toolchain only when the build config does not select one.
    defaults = environment.mono_config(dev_config)
    for key in ('mono_runtime', 'mono_compiler', 'cecil'):
        if key not in config and key in defaults:
            config[key] = defaults[key]
    if not all(config.get(key) for key in ('mono_runtime', 'mono_compiler', 'cecil')):
        raise ValueError('Local build needs explicit mono_runtime, mono_compiler and cecil paths')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    clean_source(commit)
    local = (ROOT / 'local-only').resolve()
    if not local.is_relative_to(ROOT.resolve()):
        raise ValueError('local-only must stay inside this checkout')
    if output is not None:
        output = environment.resolve_path(output, ROOT).resolve()
        if output == local or not output.is_relative_to(local) or output.exists():
            raise ValueError('Choose a new output directory under local-only')
    selected = environment.discover_python(dev_config, ROOT)
    inputs = input_identity(config, selected)
    inputs_sha = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    gate_config = dict(dev_config, **{key: config[key] for key in ('mono_runtime', 'mono_compiler', 'cecil')})
    checks = environment.test_source(gate_config, root=ROOT)
    checks['source_commit'] = commit
    if checks.get('python_checks') != 'passed' or checks.get('standalone_csharp') != 'passed':
        raise ValueError('Local candidates require the full source gate, including standalone C#')
    clean_source(commit)
    if output is None:
        local.mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix=f'local-build-{target}-{version}-{commit[:8]}-', dir=local))
    else:
        output.mkdir(parents=True, exist_ok=False)
    save(output / 'source-tests.json', checks)
    process_environment = dict(os.environ, **selected.get('environment', {}))
    def run(tool, *args):
        subprocess.run(selected['command'] + [str(ROOT / 'tools' / tool), *map(str, args)],
                       cwd=ROOT, check=True, env=process_environment)
    status = dict(source_commit=commit, version=version, target=target, build_inputs_sha256=inputs_sha, stage='build')
    try:
        # Only this invocation's intermediate files are disposable. Shared pristine
        # originals and the verified full font remain untouched for the next build.
        with tempfile.TemporaryDirectory(prefix='.work-', dir=output) as temporary:
            work = Path(temporary)
            save(work / 'build-config.json', config)
            build_dir = work / 'build'
            run('independent.py', '--config', work / 'build-config.json', '--output', build_dir, '--version', version)
            clean_source(commit)
            manifest_path = build_dir / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            if (manifest.get('source_commit') != commit or manifest.get('source_dirty') is not False
                    or manifest.get('target_id') != config['target_id'] or manifest.get('patch_version') != version):
                raise ValueError('Local build source, version or target changed')
            provenance = dict(source_repo=SOURCE_REPO, source_commit=commit, source_dirty=False,
                              build_inputs_sha256=inputs_sha)
            save(manifest_path, dict(manifest, **provenance))
            status['stage'] = 'package'
            package = work / (TARGETS[target]['prefix'] + '-' + version)
            run('package_player.py', '--config', build_dir / 'install-config.json', '--output', package)
            status['stage'] = 'verify'
            player, manifest_sha = package_identity(package)
            if input_identity(config, selected) != inputs:
                raise ValueError('Local build inputs changed during the build')
            clean_source(commit)
            archive = Path(str(package) + '.zip')
            archive_sha = digest(archive)
            # Only expose a candidate directory after the same ZIP gate used by cloud builds.
            with tempfile.TemporaryDirectory(prefix='.candidate-', dir=output) as temporary:
                stage = Path(temporary)
                archive.rename(stage / archive.name)
                save(stage / 'build-info.json', dict(
                    provenance, version=version, target_id=player['target_id'], build_origin='local',
                    local_inputs=inputs, archive=archive.name, archive_sha256=archive_sha,
                    manifest_sha256=manifest_sha, payload_sha256={row['file']: row['after'] for row in player['files']}))
                (stage / 'SHA256SUMS.txt').write_text(archive_sha + '  ' + archive.name + '\n')
                verify_download(stage, commit, version, inputs_sha, target, ROOT)
                clean_source(commit)
                candidate = output / 'candidate'
                stage.rename(candidate)
    except BaseException as error:
        save(output / 'build-status.json', dict(status, outcome='failed', error=type(error).__name__, reason=str(error)[-1000:]))
        raise
    save(output / 'build-status.json', dict(status, outcome='verified'))
    print('PASS local candidate:', candidate, '\nLocal HEAD:', commit, '(no push or install)')
    return candidate
