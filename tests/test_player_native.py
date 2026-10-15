"""Native full-package replay and signing boundaries, with tiny Mach-O fixtures."""
from pathlib import Path
import copy,io,json,re,shutil,subprocess,sys,tempfile,unittest,zipfile,os
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import player_install as player
import package_player,verify_package
from player_fixture import fixture,macho,sha,snapshot
PROCESS_IDLE=player.idle

class NativeInstall(unittest.TestCase):
    def setUp(self):
        fp=patch.dict(player.FINGERPRINTS,{player.MACOS:sha(macho())});fp.start();self.addCleanup(fp.stop)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);exe=Path(temp.name)/'exe';exe.write_bytes(macho())
        code=patch.object(player,'MAC_CODE',player.mac_code_hash(exe));code.start();self.addCleanup(code.stop)
        idle=patch.object(player,'idle');idle.start();self.addCleanup(idle.stop)

    def test_original_and_signed_code_match_but_other_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder),native=True);exe=game/manifest['executable']
            exe.write_bytes(macho(b'NEW SIGNATURE SIZE'));player.check_game_identity(game,manifest)
            exe.write_bytes(macho(b'PARTIAL SIGNATURE')[:-5]);player.check_game_identity(game,manifest)
            exe.write_bytes(macho(b'SIGNATURE',b'CHANGED CODE'))
            with self.assertRaisesRegex(RuntimeError,'版本不匹配'):player.check_game_identity(game,manifest)
            exe.write_bytes(b'MALFORMED')
            with self.assertRaises(ValueError):player.check_game_identity(game,manifest)

    def test_bundle_changes_sign_once_repeat_and_external_update_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder),native=True);commands=[]
            def run(args,**kwargs):
                commands.append(args)
                if '--force' in args:(game/manifest['executable']).write_bytes(macho(b'ADHOC'))
                return subprocess.CompletedProcess(args,0,'','')
            with patch.object(player.subprocess,'run',side_effect=run):
                player.install(game,manifest,package);player.install(game,manifest,package)
                self.assertEqual(sum('--force' in c for c in commands),1)
                runtime=package/player.ADDED;runtime.write_bytes(b'EXTERNAL UPDATE')
                next(r for r in manifest['files'] if r['file']==player.ADDED).update(after=sha(b'EXTERNAL UPDATE'),bytes=15)
                player.install(game,manifest,package)
                self.assertEqual(sum('--force' in c for c in commands),1)

    def test_partial_existing_write_and_failed_signing_are_fixed_by_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder),native=True);core=game/manifest['data_dir']/'Managed/Assembly-CSharp.dll';write=player.write_existing
            attr='com.cw3.fixture' if sys.platform=='darwin' else 'user.cw3.fixture';player.set_xattr(core,attr,b'KEEP');core.chmod(0o755);before=player.metadata(core)
            def partial(source,target,meta):
                target.write_bytes(b'PARTIAL');raise OSError('interrupted')
            with patch.object(player,'write_existing',side_effect=partial),self.assertRaises(OSError):player.install(game,manifest,package)
            self.assertEqual(core.read_bytes(),b'PARTIAL')
            bad=True
            def failed_sign(args,**kwargs):
                nonlocal bad
                if '--force' in args:
                    (game/manifest['executable']).write_bytes(macho(b'ADHOC'))
                    if bad:bad=False;raise subprocess.CalledProcessError(1,args)
                return subprocess.CompletedProcess(args,1 if bad else 0,'','')
            with patch.object(player.subprocess,'run',side_effect=failed_sign),self.assertRaises(subprocess.CalledProcessError):player.install(game,manifest,package)
            with patch.object(player.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','')),patch.object(player,'signing') as sign:
                player.install(game,manifest,package);sign.assert_called_once()
            self.assertEqual(player.metadata(core),before)
            for row in manifest['files']:self.assertEqual(player.digest(player.installed_path(game,row['file'],manifest)),row['after'])
            self.assertFalse((game/'.cw3-zh-backup').exists())

    def test_downgrade_to_internal_runtime_removes_external_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder),native=True)
            with patch.object(player.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
                player.install(game,manifest,package)
                old=copy.deepcopy(manifest);old['files']=[r for r in old['files'] if r['file']!=player.ADDED]
                row=next(r for r in old['files'] if r['file']==player.DEFAULT_DICTIONARY)
                row['file']=player.LEGACY_DICTIONARY
                (package/player.DEFAULT_DICTIONARY).rename(package/player.LEGACY_DICTIONARY)
                player.install(game,old,package)
            self.assertFalse((game/player.ADDED).exists())
            self.assertFalse((game/player.DEFAULT_DICTIONARY).exists())
            self.assertTrue((game/player.LEGACY_DICTIONARY).exists())
            self.assertEqual((game/'save.sentinel').read_bytes(),b'USER SAVE')

    def test_shared_controlled_font_is_refused_before_any_install_write(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder),native=True)
            font=game/'CW3Localization/font.ttf';font.parent.mkdir(parents=True,exist_ok=True);font.write_bytes(b'CUSTOM FONT')
            custom=font.parent/'fonts/custom.ttf';custom.parent.mkdir();os.link(font,custom);before=snapshot(game)
            with self.assertRaisesRegex(RuntimeError,'硬链接'):player.install(game,manifest,package)
            self.assertEqual(snapshot(game),before);self.assertEqual(custom.read_bytes(),b'CUSTOM FONT')

    def test_new_hardlink_after_path_check_is_refused_on_open_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);font=root/'font.ttf';font.write_bytes(b'CUSTOM FONT');custom=root/'custom.ttf';source=root/'new.ttf';source.write_bytes(b'NEW PROGRAM FONT')
            expected=player.metadata(font);open_file=Path.open
            def linked_on_open(path,*args,**kwargs):
                if path==font and args==('r+b',):os.link(font,custom)
                return open_file(path,*args,**kwargs)
            with patch.object(Path,'open',new=linked_on_open),self.assertRaisesRegex(RuntimeError,'硬链接'):
                player.write_existing(source,font,expected)
            self.assertEqual(font.read_bytes(),b'CUSTOM FONT');self.assertEqual(custom.read_bytes(),b'CUSTOM FONT')

    def test_links_and_wrong_platform_are_refused_before_any_writes(self):
        for kind in ('linked_file','linked_parent','platform'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                game,package,manifest=fixture(Path(folder),native=True)
                if kind=='platform':manifest['platform']=5
                elif kind=='linked_parent':
                    target=game/'CW3Localization';target.symlink_to(package/'CW3Localization',target_is_directory=True)
                else:
                    target=game/manifest['data_dir']/'Managed/Assembly-CSharp.dll';target.unlink();target.symlink_to(package/'CW3_Data/Managed/Assembly-CSharp.dll')
                before=snapshot(game)
                with self.assertRaises(ValueError):player.install(game,manifest,package)
                self.assertEqual(snapshot(game),before)

    def test_native_process_gate_matches_main_executable(self):
        process='123 /Applications/Games/CW3.app/Contents/MacOS/CW3'
        def run(args,**kwargs):self.assertIsNotNone(re.search(args[2],process));return subprocess.CompletedProcess(args,0,process,'')
        # Restore the real matcher for this boundary test.
        with patch.object(player.sys,'platform','darwin'),patch.object(player.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(RuntimeError,'完全退出'):PROCESS_IDLE()

    def test_native_package_retains_target_and_requires_external_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game,files,manifest=fixture(root,native=True)
            supported=json.loads((ROOT/'resources/macos-target.json').read_text());supported['exe_sha256']=manifest['exe_sha256']
            build=dict(manifest,format=1,revision='independent-v12-candidate',patch_version='native-fixture',steam_build=supported['steam_build'],version=supported['version'])
            (files/'manifest.json').write_text(json.dumps(build));original=root/'original'
            for row in manifest['files']:
                if row['before']:
                    target=original/row['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(player.installed_path(game,row['file'],manifest),target)
            for relative in package_player.PLAYER_SOURCES.values():
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,target)
            (root/'resources').mkdir();(root/'resources/macos-target.json').write_text(json.dumps(supported))
            config=root/'config.json';config.write_text(json.dumps(dict(package=str(files),build=str(files),original=str(original))))
            out=root/'local-only/package'
            with patch.object(package_player,'ROOT',root),patch.object(sys,'argv',['pack','--config',str(config),'--output',str(out)]):package_player.main()
            with zipfile.ZipFile(str(out)+'.zip') as archive,patch.object(verify_package,'ROOT',root):
                _,packed=verify_package.inspect_zip(archive,build,supported,game/manifest['executable'])
                self.assertEqual(player.target_identity(packed),player.target_identity(manifest))
                self.assertIn('清理汉化程序',archive.read('package/使用说明.txt').decode())
                wrong=dict(supported,target_id=player.WINDOWS,**player.TARGETS[player.WINDOWS])
                with self.assertRaises(ValueError):verify_package.inspect_zip(archive,build,wrong,None)
            with self.assertRaisesRegex(ValueError,'external runtime'):package_player.validate_release_payload(player.PAYLOAD-{player.ADDED},player.MACOS)
if __name__=='__main__':unittest.main()
