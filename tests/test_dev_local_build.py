"""Local candidate orchestration with real packaging/ZIP checks and tiny fake inputs."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dev
import dev_environment
import dev_local_build as local
import game_target
from package_player import PLAYER_SOURCES, INSTRUCTION_SOURCES

CHECKS = dict(python_checks='passed', standalone_csharp='passed')
VERSION = 'v12.15'
FAKE_BUILD = '''import argparse,json,os,subprocess
from pathlib import Path
import fixture_pythonpath
from player_install import PAYLOAD,ADDED,target_identity
from player_fixture import registry,sha
p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--output');p.add_argument('--version');a=p.parse_args()
root=Path(__file__).resolve().parents[1];c=json.loads(Path(a.config).read_text());out=Path(a.output);out.mkdir()
case=os.environ.get('CW3_FIXTURE_CASE','');native=c['target_id'].startswith('macos')
if case=='failed':raise SystemExit(1)
supported=json.loads((root/'resources'/('macos-target.json' if native else 'supported-build.json')).read_text())
names=PAYLOAD if native else PAYLOAD-{ADDED};runtime='CW3Localization/Runtime/CW3ExternalRuntime.dll' if native else 'CW3_Data/Managed/CW3Runtime.dll'
contents={name:('synthetic '+name).encode() for name in names};fonts=registry();fonts['runtime_sha256']=sha(contents[runtime]) if case!='runtime_pair' else '0'*64
contents['CW3Localization/fonts.json']=json.dumps(fonts).encode();rows=[]
for name,data in contents.items():
 path=out/'files'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 rows.append(dict(file=name,before=None,after=sha(data),bytes=len(data)))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
manifest=dict(format=1,revision='independent-v12-candidate',source_commit=commit,source_dirty=False,patch_version=a.version,version=supported['version'],steam_build=supported['steam_build'],files=rows,**target_identity(supported))
if case=='wrong_source':manifest['source_commit']='a'*40
if case=='wrong_version':manifest['patch_version']='v0.0'
if case=='wrong_target':manifest['target_id']='windows-steam-22453699'
if case=='dirty':manifest['source_dirty']=True
if case=='input_change':(Path(c['original'])/'CW3_Data/anchor').write_bytes(b'changed')
if case=='source_change':(root/'NOTICE.md').write_text('changed')
(out/'manifest.json').write_text(json.dumps(manifest));(out/'install-config.json').write_text(json.dumps(dict(c,package=str(out),build=str(out/'files'))))
'''


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


class LocalCandidate(unittest.TestCase):
    def fixture(self, root, target='macos', case=''):
        names = set(PLAYER_SOURCES.values()) | set(INSTRUCTION_SOURCES.values()) | {
            'tools/package_player.py', 'tools/font_registry.py', 'tools/translation_contract.py',
            'resources/macos-target.json', 'resources/supported-build.json', 'resources/layout.json'}
        for name in names:
            path = root / name;path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
        shutil.copy2(ROOT / 'tests/player_fixture.py', root / 'tools/player_fixture.py')
        (root / 'tools/independent.py').write_text(FAKE_BUILD)
        (root / '.gitignore').write_text('local-only/\nconfig.local.json\n__pycache__/\n')
        originals = root / 'local-only/original/CW3_Data';originals.mkdir(parents=True)
        (originals / 'anchor').write_bytes(b'original')
        profile = root / 'resources' / ('macos-target.json' if target == 'macos' else 'layout.json')
        data = json.loads(profile.read_text());data['original_hashes'] = {'CW3_Data/anchor': hashlib.sha256(b'original').hexdigest()}
        profile.write_text(json.dumps(data))
        font = root / 'local-only/independent-font/font.ttf';font.parent.mkdir()
        font.write_bytes(b'full OFL fixture')
        (root / 'fonts/provenance.json').write_text(json.dumps({'external_full_sha256': local.digest(font)}))
        config = dict(target_id=target + '-steam-22453699', original=str(originals.parent))
        for name in ('mono_runtime', 'mono_compiler', 'cecil'):
            path = root / 'local-only' / name;path.write_bytes(name.encode());config[name] = str(path)
        (root / 'config.local.json').write_text(json.dumps(config))
        pythonpath = root / 'local-only/pythonpath';pythonpath.mkdir()
        (pythonpath / 'fixture_pythonpath.py').write_text('')
        git(root, 'init', '-b', 'local-only-source');git(root, 'config', 'user.name', 'Fixture')
        git(root, 'config', 'user.email', 'fixture@example.invalid');git(root, 'config', 'core.fsmonitor', 'false')
        git(root, 'add', '.');git(root, 'commit', '-qm', 'Local unpublished source')
        selected = dict(command=[sys.executable], details=dict(version='3.fixture', packages={'fixture': '1'}),
                        environment=dict(PYTHONPATH=str(pythonpath), CW3_FIXTURE_CASE=case))
        return config, selected

    def build(self, root, selected, target='macos', output=None):
        with patch.object(local, 'ROOT', root), patch.object(game_target, 'ROOT', root), \
                patch.object(dev_environment, 'discover_python', return_value=selected), \
                patch.object(dev_environment, 'test_source', return_value=dict(CHECKS)) as gate:
            candidate = local.build(VERSION, target, {}, output=output)
        self.assertEqual(gate.call_count, 1)
        build_config = json.loads((root / 'config.local.json').read_text())
        for key in ('mono_runtime', 'mono_compiler', 'cecil'):
            self.assertEqual(gate.call_args.args[0][key], build_config[key])
        return candidate

    def test_clean_unpublished_head_builds_both_targets_and_unpacks(self):
        for target in ('macos', 'windows'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as folder:
                root = Path(folder);config, selected = self.fixture(root, target)
                candidate = self.build(root, selected, target)
                info = json.loads((candidate / 'build-info.json').read_text())
                self.assertEqual(info['source_commit'], git(root, 'rev-parse', 'HEAD'))
                self.assertFalse(info['source_dirty']);self.assertEqual(info['build_origin'], 'local')
                self.assertEqual(info['local_inputs']['kind'], 'local-file-inventory')
                self.assertNotIn(str(root), json.dumps(info))
                encoded = json.dumps(info['local_inputs'], sort_keys=True, separators=(',', ':')).encode()
                self.assertEqual(info['build_inputs_sha256'], hashlib.sha256(encoded).hexdigest())
                self.assertEqual({p.name for p in candidate.parent.iterdir()}, {'candidate', 'source-tests.json', 'build-status.json'})
                package = dev.unpack_candidate(candidate)
                manifest, _ = local.package_identity(package)
                self.assertEqual(manifest['version'], VERSION)
                self.assertEqual(manifest['target_id'], target + '-steam-22453699')
                self.assertEqual(git(root, 'remote'), '')
                self.assertEqual(git(root, 'status', '--porcelain'), '')
                self.assertEqual(Path(config['original']).joinpath('CW3_Data/anchor').read_bytes(), b'original')

    def test_invalid_preflight_never_builds_or_runs_source_gate(self):
        for case in ('missing_config', 'wrong_target', 'missing_original', 'changed_original', 'changed_font',
                     'missing_cecil', 'dirty', 'untracked', 'existing_output', 'outside_output', 'linked_output'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder);config, selected = self.fixture(root)
                path = root / 'config.local.json';output = root / 'local-only/result'
                if case == 'missing_config':path.unlink()
                elif case == 'wrong_target':config['target_id'] = game_target.WINDOWS
                elif case == 'missing_original':config.pop('original')
                elif case == 'changed_original':(Path(config['original']) / 'CW3_Data/anchor').write_bytes(b'patched')
                elif case == 'changed_font':(root / 'local-only/independent-font/font.ttf').write_bytes(b'wrong')
                elif case == 'missing_cecil':config.pop('cecil')
                elif case == 'dirty':(root / 'NOTICE.md').write_text('dirty')
                elif case == 'untracked':(root / 'new-source.cs').write_text('untracked')
                elif case == 'existing_output':output.mkdir();(output / 'keep').write_text('existing')
                elif case == 'outside_output':output = root / 'outside'
                elif case == 'linked_output':
                    (root / 'local-only/link').symlink_to(root, target_is_directory=True)
                    output = root / 'local-only/link/outside'
                if case in ('wrong_target', 'missing_original', 'missing_cecil'):path.write_text(json.dumps(config))
                with patch.object(local, 'ROOT', root), patch.object(game_target, 'ROOT', root), \
                        patch.object(dev_environment, 'discover_python', return_value=selected), \
                        patch.object(dev_environment, 'test_source') as gate:
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        local.build(VERSION, 'macos', {}, output=output)
                    gate.assert_not_called()
                self.assertFalse(any((root / 'local-only').glob('local-build-*')))
                if case == 'existing_output':self.assertEqual((output / 'keep').read_text(), 'existing')

    def test_changed_source_input_or_runtime_pair_never_publishes_candidate(self):
        for case in ('failed', 'wrong_source', 'wrong_version', 'wrong_target', 'dirty', 'input_change', 'source_change', 'runtime_pair'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder);_, selected = self.fixture(root, case=case)
                output = root / 'local-only/work'
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    self.build(root, selected, output=output)
                self.assertFalse((output / 'candidate').exists())
                self.assertEqual({p.name for p in output.iterdir()}, {'source-tests.json', 'build-status.json'})
                self.assertEqual(json.loads((output / 'build-status.json').read_text())['outcome'], 'failed')
                self.assertTrue((root / 'local-only/independent-font/font.ttf').is_file())

    def test_source_gate_moving_to_another_clean_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);_, selected = self.fixture(root)
            def changed_gate(*args, **kwargs):
                (root / 'NOTICE.md').write_text('new source after gate started')
                git(root, 'add', '.');git(root, 'commit', '-qm', 'Different clean HEAD')
                return dict(CHECKS)
            with patch.object(local, 'ROOT', root), patch.object(game_target, 'ROOT', root), \
                    patch.object(dev_environment, 'discover_python', return_value=selected), \
                    patch.object(dev_environment, 'test_source', side_effect=changed_gate):
                with self.assertRaisesRegex(ValueError, 'exact clean source commit'):
                    local.build(VERSION, 'macos', {})
            self.assertFalse(any((root / 'local-only').glob('local-build-*')))


class LocalCommand(unittest.TestCase):
    def test_explicit_local_build_needs_no_ref_and_never_dispatches_cloud(self):
        with patch.object(sys, 'argv', ['dev.py', 'build', '--kind', 'rendering', '--local', '--version', VERSION]), \
                patch.object(local, 'build', return_value=Path('candidate')) as build, patch.object(dev, 'cloud_build') as cloud:
            dev.main()
        cloud.assert_not_called()
        self.assertEqual(build.call_args.args[:2], (VERSION, 'macos'))

    def test_local_run_delegates_one_pinned_gate_and_records_its_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);candidate = root / 'candidate';candidate.mkdir()
            (root / 'source-tests.json').write_text(json.dumps(CHECKS))
            with patch.object(sys, 'argv', ['dev.py', '--session', str(root / 'session'), 'run', '--kind', 'package', '--local', '--version', VERSION, '--target', 'windows']), \
                    patch.object(dev, 'ROOT', root), patch.object(dev, 'desktop_lock', return_value=dev.nullcontext()), \
                    patch.object(local, 'build', return_value=candidate) as build, \
                    patch.object(dev_environment, 'test_source') as gate, patch.object(dev, 'cloud_build') as cloud:
                dev.main()
            build.assert_called_once();gate.assert_not_called();cloud.assert_not_called()
            self.assertEqual(json.loads((root / 'local-only/evidence/source-tests.json').read_text()), CHECKS)

    def test_ambiguous_or_partial_local_requests_fail_before_any_work(self):
        for flags in (['--local', '--ref', 'branch', '--version', VERSION], ['--local'],
                      ['--build-config', 'config.local.json', '--version', VERSION, '--ref', 'branch'],
                      ['--local', '--version', VERSION, '--python-only']):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as folder:
                with patch.object(sys, 'argv', ['dev.py', '--session', folder + '/session', 'run', '--kind', 'package', *flags]), \
                        patch.object(dev, 'desktop_lock', return_value=dev.nullcontext()), \
                        patch.object(dev_environment, 'test_source') as gate, patch.object(local, 'build') as build:
                    with self.assertRaises(SystemExit):dev.main()
                    gate.assert_not_called();build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
