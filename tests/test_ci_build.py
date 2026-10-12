"""Pinning and package provenance at real Git/ZIP boundaries, without game inputs."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from ci_build import plan
from unittest.mock import patch
import verify_package


class PinnedBuild(unittest.TestCase):
    def test_exact_clean_commit_and_fresh_output_required(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
            git('init', '-b', 'main')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (root/'source').write_text('source')
            git('add', '.')
            git('commit', '-m', 'Fixture')
            commit = git('rev-parse', 'HEAD')
            self.assertEqual(plan(root, 'v12.6', commit, 'a'*64)['source_commit'], commit)
            for tag, sha in [('v12.6;echo bad', commit), ('v12.6', commit[:8]), ('v12.6', 'b'*40)]:
                with self.assertRaises(ValueError):plan(root, tag, sha, 'a'*64)
            (root/'source').write_text('changed')
            with self.assertRaises(ValueError):plan(root, 'v12.6', commit, 'a'*64)
            git('checkout', '--', 'source')
            (root/'local-only/ci-release').mkdir(parents=True)
            with self.assertRaises(ValueError):plan(root, 'v12.6', commit, 'a'*64)

    def test_player_zip_retains_source_and_payload_hashes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in ['tools/package_player.py','tools/player_install.py','resources/supported-build.json',
                         'player/安装或恢复.command','player/安装或恢复.cmd','player/使用说明-v12.txt',
                         'fonts/OFL.txt','LICENSE','NOTICE.md','docs/text-style.md']:
                target=root/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,target)
            original=root/'original';original.mkdir()
            build=root/'build';build.mkdir()
            (original/'file').write_bytes(b'original');(build/'file').write_bytes(b'patch')
            sha=lambda data:hashlib.sha256(data).hexdigest()
            provenance=dict(source_repo='m1m0ry/cw3-localization-public',source_commit='a'*40,
                            source_dirty=False,build_inputs_sha256='b'*64)
            supported=json.loads((root/'resources/supported-build.json').read_text())
            manifest=dict(provenance,format=1,revision='independent-v12-candidate',patch_version='v12.6',
                          steam_build=supported['steam_build'],version=supported['version'],
                          files=[dict(file='file',before=sha(b'original'),after=sha(b'patch'),bytes=5)])
            (build/'manifest.json').write_text(json.dumps(manifest))
            config=root/'config.json';config.write_text(json.dumps(dict(package=str(build),build=str(build),original=str(original),game=str(original))))
            output=root/'local-only/package'
            subprocess.run([sys.executable,str(root/'tools/package_player.py'),'--config',str(config),'--output',str(output)],check=True,capture_output=True)
            with zipfile.ZipFile(str(output)+'.zip') as z:
                player=json.loads(z.read('package/manifest.json'))
                for key,value in provenance.items():self.assertEqual(player[key],value)
                self.assertEqual(player['files'],manifest['files'])
                self.assertEqual(sha(z.read('package/file')),player['files'][0]['after'])
                self.assertEqual({name.split('/',1)[1] for name in z.namelist()},{'file','manifest.json','install.py','安装或恢复.command','安装或恢复.cmd','使用说明.txt','OFL.txt','LICENSE','NOTICE.md','字体设置.md'})
                with patch.object(verify_package,'ROOT',root):
                    _,inspected=verify_package.inspect_zip(z,manifest,supported,None)
                    self.assertEqual(inspected['source_commit'],provenance['source_commit'])
                    invalid_exe=root/'invalid-exe';invalid_exe.write_bytes(b'wrong executable')
                    with self.assertRaisesRegex(ValueError,'CW3.exe does not match'):
                        verify_package.inspect_zip(z,manifest,supported,invalid_exe)
            checked=subprocess.run([sys.executable,str(ROOT/'tools/verify_package.py'),'--config',str(config),
                                    '--package',str(output)+'.zip','--inspect-only'],check=True,capture_output=True,text=True)
            self.assertIn('Actual executable unavailable',checked.stdout)
            # Target strings follow the same supported-build metadata in both
            # packaging and verification, rather than duplicating game numbers.
            supported.update(version='9.99 Steam',steam_build='fixture-build',unity_version='fixture-unity')
            (root/'resources/supported-build.json').write_text(json.dumps(supported))
            manifest.update(version=supported['version'],steam_build=supported['steam_build'])
            (build/'manifest.json').write_text(json.dumps(manifest));other=root/'local-only/other-target'
            subprocess.run([sys.executable,str(root/'tools/package_player.py'),'--config',str(config),'--output',str(other)],check=True,capture_output=True)
            with zipfile.ZipFile(str(other)+'.zip') as z,patch.object(verify_package,'ROOT',root):
                _,player=verify_package.inspect_zip(z,manifest,supported,None)
                self.assertEqual(player['target'],'Windows Steam 9.99 / build fixture-build / Unity fixture-unity')



if __name__ == '__main__':unittest.main()
