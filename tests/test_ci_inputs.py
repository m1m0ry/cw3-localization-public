"""Fixed input preparation at real Git and ZIP boundaries; no game files."""
from pathlib import Path
import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_inputs

sha = lambda data: hashlib.sha256(data).hexdigest()


class FixedInputs(unittest.TestCase):
    def fixture(self, root, target, corruption=None):
        (root / 'resources').mkdir()
        (root / 'fonts').mkdir()
        files = {'font.ttf': b'fixture font', 'tools/mcs.exe': b'fixture compiler',
                 'tools/Mono.Cecil.dll': b'fixture cecil',
                 'original/CW3_Data/Managed/Assembly-CSharp.dll': target.encode()}
        hashes = {name: sha(data) for name, data in files.items()}
        for platform in ('windows', 'macos'):
            profile = 'macos-target.json' if platform == 'macos' else 'layout.json'
            (root / 'resources' / profile).write_text(json.dumps(dict(original_hashes={
                'CW3_Data/Managed/Assembly-CSharp.dll': sha(platform.encode())})))
        (root / 'fonts/provenance.json').write_text(json.dumps(dict(external_full_sha256=hashes['font.ttf'])))
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        git('add', '.')
        git('commit', '-m', 'Synthetic fixture')
        commit = git('rev-parse', 'HEAD')
        metadata = dict(repository='m1m0ry/cw3-localization', release_id=1, tag='fixed',
                        tools={name: value for name, value in hashes.items() if name.startswith('tools/')},
                        targets={target: dict(asset_id=2, asset='fixture.zip')})
        rows = [dict(file=name, bytes=len(data), sha256=hashes[name]) for name, data in files.items()]
        if corruption == 'manifest':
            rows[0]['sha256'] = '0' * 64
        if corruption == 'mixed_platform':
            files['original/CW3_Data/Managed/Assembly-CSharp.dll'] = b'mixed platform'
            rows[-1].update(bytes=len(b'mixed platform'), sha256=sha(b'mixed platform'))
        if corruption == 'content':
            files['tools/mcs.exe'] = b'corrupt compiler'
        if corruption == 'extra':
            files['../outside'] = b'outside'
        archive = root / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('inputs.json', json.dumps(dict(files=rows)))
            for name, data in files.items():
                entry = zipfile.ZipInfo(name)
                if corruption == 'symlink' and name == 'font.ttf':
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                output.writestr(entry, data)
            if corruption == 'duplicate':
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    output.writestr('font.ttf', files['font.ttf'])
        metadata['targets'][target].update(bytes=archive.stat().st_size, sha256=sha(archive.read_bytes()))
        if corruption == 'archive':
            archive.write_bytes(b'invalid archive')
        return archive, commit, metadata

    def test_both_platforms_prepare_exact_verified_inputs_and_native_mono_config(self):
        for target in ci_inputs.TARGETS:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive, commit, metadata = self.fixture(root, target)
                ci_inputs.prepare(archive, root, commit, target, metadata)
                local = root / 'local-only'
                self.assertEqual((local / 'independent-font/font.ttf').read_bytes(), b'fixture font')
                config = json.loads((local / 'ci-config.json').read_text())
                self.assertEqual(config['target_id'], target + '-steam-22453699')
                self.assertEqual(config['mono_runtime'], '/usr/bin/mono')
                self.assertEqual(Path(config['mono_compiler']), local / 'ci-inputs/tools/mcs.exe')
                self.assertEqual({p.name for p in local.iterdir()}, {'ci-inputs', 'independent-font', 'ci-config.json'})
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    ci_inputs.prepare(archive, root, commit, target, metadata)

    def test_wrong_source_mixed_or_malformed_inputs_leave_no_prepared_output(self):
        for target in ci_inputs.TARGETS:
            for corruption in ('commit', 'short_commit', 'archive', 'manifest', 'mixed_platform',
                               'content', 'extra', 'duplicate', 'symlink'):
                with self.subTest(target=target, corruption=corruption), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    archive, commit, metadata = self.fixture(root, target, corruption)
                    requested = 'b' * 40 if corruption == 'commit' else commit[:8] if corruption == 'short_commit' else commit
                    with self.assertRaises(ValueError):
                        ci_inputs.prepare(archive, root, requested, target, metadata)
                    local = root / 'local-only'
                    self.assertFalse(local.exists() and list(local.iterdir()))
                    self.assertFalse((root / 'outside').exists())

    def test_missing_token_or_unpublished_mismatched_asset_never_downloads(self):
        metadata = dict(repository='m1m0ry/cw3-localization', release_id=1, tag='fixed', targets={
            'windows': dict(asset_id=2, asset='fixture.zip', bytes=5, sha256='a' * 64)})
        good = dict(id=1, tag_name='fixed', draft=False, assets=[dict(
            id=2, name='fixture.zip', size=5, digest='sha256:' + 'a' * 64, state='uploaded')])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'download.zip'
            with patch.dict(os.environ, {}, clear=True), patch.object(ci_inputs.subprocess, 'check_output') as network:
                with self.assertRaisesRegex(ValueError, 'CW3_INPUTS_READ_TOKEN'):
                    ci_inputs.fetch(path, 'windows', metadata)
                network.assert_not_called()
            for corruption in ('public', 'draft', 'release', 'tag', 'asset', 'name', 'size', 'digest', 'state'):
                release = copy.deepcopy(good)
                repo = dict(private=corruption != 'public')
                if corruption == 'draft':release['draft'] = True
                if corruption == 'release':release['id'] = 9
                if corruption == 'tag':release['tag_name'] = 'other'
                if corruption == 'asset':release['assets'] = []
                if corruption in ('name', 'size', 'digest', 'state'):
                    release['assets'][0][corruption] = 'wrong'
                with self.subTest(corruption=corruption), patch.dict(os.environ, GH_TOKEN='fixture-only'):
                    with patch.object(ci_inputs.subprocess, 'check_output', side_effect=[json.dumps(repo), json.dumps(release)]), patch.object(ci_inputs.subprocess, 'run') as download:
                        with self.assertRaises(ValueError):ci_inputs.fetch(path, 'windows', metadata)
                        download.assert_not_called()
                        self.assertFalse(path.exists())
            with patch.dict(os.environ, GH_TOKEN='fixture-only'):
                def downloaded(command, **kwargs):
                    self.assertEqual(command[:4], ['gh', 'api', '--hostname', 'github.com'])
                    self.assertIn('repos/m1m0ry/cw3-localization/releases/assets/2', command)
                    self.assertNotIn('fixture-only', command)
                    kwargs['stdout'].write(b'input')
                with patch.object(ci_inputs.subprocess, 'check_output', side_effect=[json.dumps(dict(private=True)), json.dumps(good)]), patch.object(ci_inputs.subprocess, 'run', side_effect=downloaded):
                    ci_inputs.fetch(path, 'windows', metadata)
                self.assertEqual(path.read_bytes(), b'input')


if __name__ == '__main__':
    unittest.main()
