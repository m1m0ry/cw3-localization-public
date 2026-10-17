"""Pinning and package provenance at real Git/ZIP boundaries, without game inputs."""
from pathlib import Path
import hashlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from ci_build import plan
from package_player import INSTRUCTION_SOURCES, instructions
from unittest.mock import patch
import verify_package


class PinnedBuild(unittest.TestCase):
    def test_platform_text_templates_only_replace_the_version_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'player').mkdir()
            for platform in ('Windows','Mac'):
                (root/'player'/('使用说明-'+platform+'.txt')).write_bytes((platform+' 中文 {version} / {version}.zip / {0}\n').encode('utf-8'))
            for platform,profile in (('Windows','supported-build.json'),('Mac','macos-target.json')):
                with self.subTest(platform=platform):
                    supported=json.loads((ROOT/'resources'/profile).read_text())
                    self.assertEqual(instructions(supported,'v99.1',root),platform+' 中文 v99.1 / v99.1.zip / {0}\n')

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
            for file in ['tools/package_player.py','tools/player_install.py','tools/font_registry.py','tools/translation_contract.py','resources/supported-build.json',
                         'player/安装汉化.command','player/安装汉化.cmd',
                         'fonts/OFL.txt','LICENSE','NOTICE.md','docs/text-style.md',*INSTRUCTION_SOURCES.values()]:
                target=root/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,target)
            original=root/'original';original.mkdir()
            build=root/'build';build.mkdir()
            from player_fixture import registry
            import player_install as installer
            sha=lambda data:hashlib.sha256(data).hexdigest()
            rows=[]
            for payload in sorted(installer.PAYLOAD-{installer.ADDED}):
                target=build/payload;target.parent.mkdir(parents=True,exist_ok=True)
                content=json.dumps(registry()).encode() if payload=='CW3Localization/fonts.json' else b'patch'
                target.write_bytes(content);rows.append(dict(file=payload,before=None,after=sha(content),bytes=len(content)))
            payload=rows[0]['file']
            provenance=dict(source_repo='m1m0ry/cw3-localization-public',source_commit='a'*40,
                            source_dirty=False,build_inputs_sha256='b'*64)
            supported=json.loads((root/'resources/supported-build.json').read_text())
            manifest=dict(provenance,format=1,revision='independent-v12-candidate',patch_version='v12.6',
                          steam_build=supported['steam_build'],version=supported['version'],
                          controlled_fonts={'sans':'legacy'},runtime_files=['legacy'],files=rows)
            manifest.update(installer.target_identity(supported))
            (build/'manifest.json').write_text(json.dumps(manifest))
            config=root/'config.json';config.write_text(json.dumps(dict(package=str(build),build=str(build),original=str(original),game=str(original))))
            output=root/'local-only/package'
            subprocess.run([sys.executable,str(root/'tools/package_player.py'),'--config',str(config),'--output',str(output)],check=True,capture_output=True,env=dict(os.environ,TZ='UTC'))
            with zipfile.ZipFile(str(output)+'.zip') as z:
                player=json.loads(z.read('package/manifest.json'))
                for key,value in provenance.items():self.assertEqual(player[key],value)
                self.assertEqual(player['files'],manifest['files'])
                self.assertNotIn('runtime_files',player)
                self.assertNotIn('controlled_fonts',player)
                self.assertEqual(sha(z.read('package/'+payload)),player['files'][0]['after'])
                self.assertEqual({name.split('/',1)[1] for name in z.namelist()},{r['file'] for r in rows}|{'manifest.json','install.py','安装汉化.command','安装汉化.cmd','使用说明.txt','OFL.txt','LICENSE','NOTICE.md','字体设置.md'})
                with patch.object(verify_package,'ROOT',root):
                    _,inspected=verify_package.inspect_zip(z,manifest,supported,None)
                    self.assertEqual(inspected['source_commit'],provenance['source_commit'])
                    invalid_game=root/'invalid-game';(invalid_game/'CW3_Data').mkdir(parents=True);(invalid_game/'CW3.exe').write_bytes(b'wrong executable')
                    with self.assertRaisesRegex(RuntimeError,'版本不匹配'):
                        verify_package.inspect_zip(z,manifest,supported,invalid_game)
            checked=subprocess.run([sys.executable,str(ROOT/'tools/verify_package.py'),'--config',str(config),
                                    '--package',str(output)+'.zip','--inspect-only'],check=True,capture_output=True,text=True)
            self.assertIn('Actual executable unavailable',checked.stdout)
            # Even a self-consistent producer/player manifest cannot authorize
            # development payloads. Exercise both independent release gates.
            clean_archive=Path(str(output)+'.zip').read_bytes()
            # Historical extra fields do not override the canonical files list.
            legacy=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(clean_archive)) as clean,zipfile.ZipFile(legacy,'w') as z:
                for name in clean.namelist():
                    data=clean.read(name)
                    if name=='package/manifest.json':
                        player=json.loads(data);player.update(runtime_files=['obsolete'],controlled_fonts={'sans':'obsolete'})
                        data=json.dumps(player).encode()
                    z.writestr(name,data)
            legacy.seek(0)
            with zipfile.ZipFile(legacy) as z,patch.object(verify_package,'ROOT',root):
                _,player=verify_package.inspect_zip(z,manifest,supported,None)
                self.assertEqual(player['files'],rows)
            for extra in ('CW3_Data/Managed/CW3Debug.dll','CW3_Data/output_log.txt'):
                polluted=copy.deepcopy(manifest);content=b'PRIVATE DEBUG OR LOG'
                row=dict(file=extra,before=None,after=sha(content),bytes=len(content));polluted['files'].append(row)
                path=build/extra;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
                (build/'manifest.json').write_text(json.dumps(polluted))
                refused=root/'local-only/refused'
                result=subprocess.run([sys.executable,str(root/'tools/package_player.py'),'--config',str(config),'--output',str(refused)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertIn('Unexpected release payload',result.stderr);self.assertFalse(refused.exists())
                crafted=io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(clean_archive)) as clean,zipfile.ZipFile(crafted,'w') as z:
                    for name in clean.namelist():
                        data=clean.read(name)
                        if name=='package/manifest.json':
                            player=json.loads(data);player['files']=polluted['files'];data=json.dumps(player).encode()
                        z.writestr(name,data)
                    z.writestr('package/'+extra,content)
                crafted.seek(0)
                with zipfile.ZipFile(crafted) as z,self.assertRaisesRegex(ValueError,'Unexpected release payload'):
                    verify_package.inspect_zip(z,polluted,supported,None)
            (build/'manifest.json').write_text(json.dumps(manifest))
            # Same contents under different filesystem metadata and timezone
            # must produce the same player archive, including executable mode.
            for source in root.rglob('*'):
                if source.is_file() and 'local-only' not in source.relative_to(root).parts:
                    os.utime(source,(1700000001,1700000001));source.chmod(0o777)
            repeat=root/'local-only/repeated/package'
            subprocess.run([sys.executable,str(root/'tools/package_player.py'),'--config',str(config),'--output',str(repeat)],check=True,capture_output=True,env=dict(os.environ,TZ='Pacific/Honolulu'))
            self.assertEqual(Path(str(output)+'.zip').read_bytes(),Path(str(repeat)+'.zip').read_bytes())
            with zipfile.ZipFile(str(repeat)+'.zip') as z:
                self.assertEqual(z.namelist(),sorted(z.namelist()))
                for info in z.infolist():
                    self.assertEqual(info.date_time,(1980,1,1,0,0,0))
                    self.assertEqual(info.create_system,3)
                    self.assertEqual((info.external_attr>>16)&0o777,0o755 if info.filename.endswith('/安装汉化.command') else 0o644)
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
