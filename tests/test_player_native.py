"""Native mapping and recovery contracts using only disposable filesystem fixtures."""
from pathlib import Path
import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import player_install as player
import package_player
import verify_package

sha=lambda value:hashlib.sha256(value).hexdigest()

class NativePlayer(unittest.TestCase):
    def changing_provenance(self,core):
        read=player.metadata;changed=False
        def observed(path):
            nonlocal changed
            value=read(path)
            if Path(path)==core and value is not None:
                if player.digest(core)!=sha(b'ORIGINAL'):changed=True
                value=dict(value,xattrs=dict(value['xattrs']))
                value['xattrs'][player.SYSTEM_XATTR]='0200' if changed else '0100'
            return value
        return observed

    def fixture(self,root):
        game=root/'native game';package=root/'package'
        manifest=dict(format=2,version='native-fixture',target_id=player.MACOS,**player.TARGETS[player.MACOS],exe_sha256=sha(b'NATIVE EXE'),files=[])
        exe=game/manifest['executable'];exe.parent.mkdir(parents=True);exe.write_bytes(b'NATIVE EXE')
        data=game/manifest['data_dir'];(data/'Managed').mkdir(parents=True)
        core=data/'Managed/Assembly-CSharp.dll';core.write_bytes(b'ORIGINAL');core.chmod(0o755)
        attr='com.cw3.fixture' if sys.platform=='darwin' else 'user.cw3.fixture'
        player.set_xattr(core,attr,b'original attributes')
        for name,content,before in [('CW3_Data/Managed/Assembly-CSharp.dll',b'PATCHED',sha(b'ORIGINAL')),
                                    ('CW3_Data/Managed/CW3Runtime.dll',b'HELPER',None),
                                    ('CW3Localization/zh-CN.json',b'DICTIONARY',None)]:
            path=package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            manifest['files'].append(dict(file=name,before=before,after=sha(content),bytes=len(content)))
        (game/'save.sentinel').write_bytes(b'USER SAVE')
        return game,package,manifest,core,attr

    @patch.object(player,'idle')
    def test_signed_native_bundle_is_rejected_before_any_write(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder))
            signature=game/'CW3.app/Contents/_CodeSignature/CodeResources'
            signature.parent.mkdir();signature.write_bytes(b'SEALED RESOURCE MANIFEST')
            before=self.snapshot(game)
            with self.assertRaisesRegex(RuntimeError,'封印签名'):
                player.install(game,manifest,None,package)
            self.assertEqual(self.snapshot(game),before)
            self.assertFalse((game/player.BACKUP).exists())

    def snapshot(self,root):
        return {p.relative_to(root).as_posix():(p.read_bytes(),player.metadata(p)) for p in root.rglob('*') if p.is_file()}

    def test_only_provenance_value_is_system_managed(self):
        original=dict(mode=0o755,xattrs={'com.apple.provenance':'0100','com.apple.quarantine':'restricted','com.cw3.fixture':'other'})
        changed=copy.deepcopy(original);changed['xattrs']['com.apple.provenance']='0200'
        self.assertTrue(player.recoverable_metadata_matches(changed,original))
        for field in ('com.apple.provenance','com.apple.quarantine','com.cw3.fixture'):
            missing=copy.deepcopy(changed);del missing['xattrs'][field]
            self.assertFalse(player.recoverable_metadata_matches(missing,original),field)
        for field in ('com.apple.quarantine','com.cw3.fixture'):
            altered=copy.deepcopy(changed);altered['xattrs'][field]='tampered'
            self.assertFalse(player.recoverable_metadata_matches(altered,original),field)
        extra=copy.deepcopy(changed);extra['xattrs']['com.example.unknown']='new'
        self.assertFalse(player.recoverable_metadata_matches(extra,original))
        changed['mode']=0o644
        self.assertFalse(player.recoverable_metadata_matches(changed,original))

    def test_explicit_target_mapping_rejects_mixed_fields_and_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder))
            self.assertEqual(player.installed_path(game,'CW3_Data/Managed/Assembly-CSharp.dll',manifest),core)
            self.assertEqual(player.safe(package,'CW3_Data/Managed/Assembly-CSharp.dll'),package/'CW3_Data/Managed/Assembly-CSharp.dll')
            for changes in (dict(target_id='auto'),dict(platform=5),dict(data_dir='CW3_Data'),dict(executable='../CW3'),dict(target_id=player.WINDOWS)):
                wrong=dict(manifest,**changes)
                with self.subTest(changes=changes),self.assertRaises(ValueError):player.install(game,wrong,None,package)
            wrong=dict(manifest);del wrong['platform']
            with self.assertRaises(ValueError):player.installed_path(game,'CW3_Data/level1',wrong)
            outside=Path(folder)/'outside';outside.mkdir();(game/'CW3.app/Contents/Resources/Data/escape').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):player.installed_path(game,'CW3_Data/escape/file',manifest)
            for name in ('CW3_Data/../../../Contents/MacOS/CW3','CW3_Data\\..\\outside','CW3_Data/file:stream'):
                with self.subTest(name=name),self.assertRaises(ValueError):player.installed_path(game,name,manifest)
            self.assertFalse((game/player.BACKUP).exists())

    @patch.object(player,'idle')
    def test_install_restore_preserves_original_metadata_and_outside_files(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            player.install(game,manifest,None,package)
            state=player.backup_info(game,manifest)
            self.assertEqual(player.status(game,manifest,state),'installed')
            self.assertEqual(player.metadata(core),before[core.relative_to(game).as_posix()][1])
            self.assertEqual({key:state[key] for key in player.IDENTITY},player.target_identity(manifest))
            self.assertFalse((game/'CW3_Data').exists())
            self.assertTrue((game/player.BACKUP).is_dir())
            player.restore(game,state)
            after={name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')}
            self.assertEqual(after,before)
            self.assertEqual(player.status(game,manifest,player.backup_info(game,manifest)),'original')

    @patch.object(player,'idle')
    def test_fresh_external_runtime_directory_is_created_after_preflight(self,_):
        for existing_content in (False,True):
            with self.subTest(existing_content=existing_content),tempfile.TemporaryDirectory() as folder:
                game,package,manifest,core,attr=self.fixture(Path(folder))
                name='CW3Localization/Runtime/CW3ExternalRuntime.dll';payload=package/name
                payload.parent.mkdir(parents=True);payload.write_bytes(b'EXTERNAL')
                manifest['files'].append(dict(file=name,before=None,after=sha(b'EXTERNAL'),bytes=8))
                if existing_content:(game/'CW3Localization').mkdir()
                self.assertFalse((game/name).parent.exists())
                player.install(game,manifest,None,package)
                self.assertEqual((game/name).read_bytes(),b'EXTERNAL')
                player.restore(game,player.backup_info(game,manifest))
                self.assertFalse((game/name).exists())
                self.assertEqual(core.read_bytes(),b'ORIGINAL')
                self.assertEqual((game/'save.sentinel').read_bytes(),b'USER SAVE')

    @patch.object(player,'idle')
    def test_external_runtime_parent_rejects_links_files_and_bad_payload_before_creation(self,_):
        for kind in ('content_link','runtime_link','runtime_file','bad_payload'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);game,package,manifest,core,attr=self.fixture(root)
                name='CW3Localization/Runtime/CW3ExternalRuntime.dll';payload=package/name
                payload.parent.mkdir(parents=True);payload.write_bytes(b'EXTERNAL')
                manifest['files'].append(dict(file=name,before=None,after=sha(b'EXTERNAL'),bytes=8))
                content=game/'CW3Localization';outside=root/'outside';outside.mkdir()
                if kind=='content_link':content.symlink_to(outside,target_is_directory=True)
                elif kind!='bad_payload':
                    content.mkdir()
                    if kind=='runtime_link':(content/'Runtime').symlink_to(outside,target_is_directory=True)
                    else:(content/'Runtime').write_bytes(b'USER FILE')
                else:payload.write_bytes(b'BROKEN')
                before=self.snapshot(game)
                with self.assertRaises((ValueError,RuntimeError)):
                    player.install(game,manifest,None,package)
                self.assertEqual(self.snapshot(game),before)
                self.assertFalse((game/player.BACKUP).exists())
                self.assertFalse(any(outside.iterdir()))
                if kind=='bad_payload':self.assertFalse(content.exists())

    @patch.object(player,'idle')
    def test_existing_inode_preserves_attributes_without_reproducing_them(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            with patch.object(player,'set_xattr',side_effect=PermissionError('attribute denied')) as write_attr:
                player.install(game,manifest,None,package)
                self.assertEqual(player.metadata(core),before[core.relative_to(game).as_posix()][1])
                player.restore(game,player.backup_info(game,manifest))
                write_attr.assert_not_called()
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)

    @patch.object(player,'idle')
    def test_system_provenance_changes_during_install_and_restore(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            with patch.object(player,'metadata',side_effect=self.changing_provenance(core)):
                player.install(game,manifest,None,package)
                state=player.backup_info(game,manifest)
                row=next(x for x in state['files'] if x['file']=='CW3_Data/Managed/Assembly-CSharp.dll')
                self.assertEqual(row['before_metadata']['xattrs'][player.SYSTEM_XATTR],'0100')
                self.assertEqual(row['after_metadata']['xattrs'][player.SYSTEM_XATTR],'0200')
                self.assertEqual(player.status(game,manifest,state),'installed')
                player.restore(game,state)
                self.assertEqual(player.metadata(core)['xattrs'][player.SYSTEM_XATTR],'0200')
                self.assertEqual(player.status(game,manifest,player.backup_info(game,manifest)),'original')
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)

    @patch.object(player,'idle')
    def test_already_restored_journal_closes_without_rewriting_game(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            player.install(game,manifest,None,package)
            state=player.backup_info(game,manifest);player.restore(game,state)
            player.put_json(game/player.BACKUP/'journal.json',dict(player.journal_record(game,state,'install',state['files']),in_progress='CW3_Data/Managed/Assembly-CSharp.dll'))
            read=player.metadata
            def changed(path):
                value=read(path)
                if Path(path)==core:
                    value=dict(value,xattrs=dict(value['xattrs']))
                    value['xattrs'][player.SYSTEM_XATTR]='0200'
                return value
            with patch.object(player,'metadata',side_effect=changed),patch.object(player,'write_existing',side_effect=AssertionError('rewrote original game file')):
                player.restore(game,state)
            self.assertFalse((game/player.BACKUP/'journal.json').exists())
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)

    @patch.object(player,'idle')
    def test_interrupted_install_rolls_back_bytes_and_metadata(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            replace=os.replace;failed=False
            def fail_once(source,target):
                nonlocal failed
                if Path(target)==game/'CW3Localization/zh-CN.json' and not failed:
                    failed=True;raise OSError('fixture interruption')
                return replace(source,target)
            with patch.object(player.os,'replace',side_effect=fail_once),self.assertRaisesRegex(OSError,'fixture interruption'):
                player.install(game,manifest,None,package)
            self.assertTrue(failed)
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)
            self.assertFalse((game/player.BACKUP/'journal.json').exists())

    @patch.object(player,'idle')
    def test_partial_existing_file_write_recovers_from_verified_backup(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            copy=shutil.copyfileobj;failed=False
            def partial(source,target,*args,**kwargs):
                nonlocal failed
                if target.name==str(core) and not failed:
                    failed=True;target.write(b'PARTIAL');raise OSError('partial native write')
                return copy(source,target,*args,**kwargs)
            with patch.object(player.shutil,'copyfileobj',side_effect=partial),self.assertRaisesRegex(OSError,'partial native write'):
                player.install(game,manifest,None,package)
            self.assertTrue(failed)
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)
            self.assertFalse((game/player.BACKUP/'journal.json').exists())

    @patch.object(player,'idle')
    def test_provenance_changed_partial_write_can_resume_from_journal(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));manifest['files'].sort(key=lambda row:row['file']);before=self.snapshot(game)
            copy=shutil.copyfileobj;failed=False
            def partial(source,target,*args,**kwargs):
                nonlocal failed
                if target.name==str(core) and not failed:
                    failed=True;target.write(b'PARTIAL');raise OSError('partial native write')
                return copy(source,target,*args,**kwargs)
            with patch.object(player,'metadata',side_effect=self.changing_provenance(core)):
                with patch.object(player.shutil,'copyfileobj',side_effect=partial),patch.object(player,'restore',side_effect=RuntimeError('process ended before rollback')):
                    with self.assertRaisesRegex(RuntimeError,'process ended before rollback'):player.install(game,manifest,None,package)
                self.assertTrue(failed)
                state=player.backup_info(game,manifest)
                self.assertEqual(player.status(game,manifest,state),'interrupted')
                self.assertTrue((game/'CW3Localization/zh-CN.json').exists())
                with patch.object(player,'write_existing',side_effect=OSError('restore interrupted again')):
                    with self.assertRaisesRegex(OSError,'restore interrupted again'):player.restore(game,state)
                self.assertEqual(player.read(game/player.BACKUP/'journal.json')['in_progress'],'CW3_Data/Managed/Assembly-CSharp.dll')
                player.restore(game,state)
                self.assertFalse((game/player.BACKUP/'journal.json').exists())
                self.assertEqual(player.metadata(core)['xattrs'][player.SYSTEM_XATTR],'0200')
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)

    @patch.object(player,'idle')
    def test_restore_refuses_unknown_metadata_or_executable_and_keeps_backup(self,_):
        for changed in ('mode','attribute','executable'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as folder:
                game,package,manifest,core,attr=self.fixture(Path(folder));player.install(game,manifest,None,package)
                state=player.backup_info(game,manifest)
                if changed=='mode':core.chmod(0o644)
                elif changed=='attribute':player.set_xattr(core,attr,b'OTHER ATTRIBUTES')
                else:(game/manifest['executable']).write_bytes(b'OTHER EXE')
                before=self.snapshot(game)
                with self.assertRaises(RuntimeError):player.restore(game,state)
                self.assertEqual(self.snapshot(game),before)
                self.assertFalse((game/player.BACKUP/'journal.json').exists())

    @patch.object(player,'idle')
    def test_interrupted_restore_can_resume_and_rejects_cross_target_journal(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest,core,attr=self.fixture(Path(folder));before=self.snapshot(game)
            player.install(game,manifest,None,package);state=player.backup_info(game,manifest)
            unlink=Path.unlink;failed=False
            helper=game/manifest['data_dir']/'Managed/CW3Runtime.dll'
            def fail_once(path,*args,**kwargs):
                nonlocal failed
                if path==helper and not failed:failed=True;raise OSError('restore interruption')
                return unlink(path,*args,**kwargs)
            with patch.object(Path,'unlink',fail_once),self.assertRaisesRegex(OSError,'restore interruption'):player.restore(game,state)
            self.assertEqual(player.status(game,manifest,state),'interrupted')
            journal=game/player.BACKUP/'journal.json';valid=player.read(journal)
            invalid=dict(valid,platform=5);player.put_json(journal,invalid);interrupted=self.snapshot(game)
            with self.assertRaises(ValueError):player.restore(game,state)
            self.assertEqual(self.snapshot(game),interrupted)
            player.put_json(journal,valid);player.restore(game,state)
            self.assertEqual({name:value for name,value in self.snapshot(game).items() if not name.startswith(player.BACKUP+'/')},before)

    def test_native_process_gate_recognizes_main_executable_without_launching_it(self):
        process='123 /Applications/Games/CW3.app/Contents/MacOS/CW3'
        def pgrep(args,**kwargs):
            self.assertEqual(args[:2],['pgrep','-fl'])
            self.assertIsNotNone(re.search(args[2],process))
            return subprocess.CompletedProcess(args,0,stdout=process+'\n',stderr='')
        with patch.object(player.sys,'platform','darwin'),patch.object(player.subprocess,'run',side_effect=pgrep):
            with self.assertRaisesRegex(RuntimeError,'完全退出'):player.idle()

    def test_native_package_retains_target_and_rejects_cross_platform_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game,package,manifest,core,attr=self.fixture(root)
            external='CW3Localization/Runtime/CW3ExternalRuntime.dll'
            payload=package/external;payload.parent.mkdir(parents=True);payload.write_bytes(b'FIXED MAC RUNTIME')
            manifest['files'].append(dict(file=external,before=None,after=sha(b'FIXED MAC RUNTIME'),bytes=len(b'FIXED MAC RUNTIME')))
            supported=json.loads((ROOT/'resources/macos-target.json').read_text());supported['exe_sha256']=manifest['exe_sha256']
            build=dict(manifest,format=1,revision='independent-v12-candidate',patch_version='native-fixture',steam_build=supported['steam_build'],version=supported['version'])
            original=root/'original';path=original/'CW3_Data/Managed/Assembly-CSharp.dll';path.parent.mkdir(parents=True);shutil.copy2(core,path)
            (package/'manifest.json').write_text(json.dumps(build))
            for relative in package_player.PLAYER_SOURCES.values():
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,target)
            (root/'resources').mkdir();(root/'resources/macos-target.json').write_text(json.dumps(supported))
            config=root/'config.json';config.write_text(json.dumps(dict(package=str(package),build=str(package),original=str(original))))
            out=root/'local-only/package'
            with patch.object(package_player,'ROOT',root),patch.object(sys,'argv',['package_player','--config',str(config),'--output',str(out)]):package_player.main()
            with zipfile.ZipFile(str(out)+'.zip') as archive,patch.object(verify_package,'ROOT',root):
                _,player_manifest=verify_package.inspect_zip(archive,build,supported,game/manifest['executable'])
                self.assertEqual(player.target_identity(player_manifest),player.target_identity(manifest))
                self.assertIn('四角色保存与取消',archive.read('package/使用说明.txt').decode())
                wrong=dict(supported,**dict(target_id=player.WINDOWS,**player.TARGETS[player.WINDOWS]))
                with self.assertRaises(ValueError):verify_package.inspect_zip(archive,build,wrong,None)
                missing_build=copy.deepcopy(build)
                missing_build['files']=[row for row in build['files'] if row['file']!=external]
                missing_player=copy.deepcopy(player_manifest);missing_player['files']=missing_build['files']
                data=io.BytesIO()
                with zipfile.ZipFile(data,'w') as damaged:
                    for info in archive.infolist():
                        if info.filename=='package/'+external:continue
                        content=json.dumps(missing_player).encode() if info.filename=='package/manifest.json' else archive.read(info)
                        damaged.writestr(info,content)
                data.seek(0)
                with zipfile.ZipFile(data) as damaged,self.assertRaisesRegex(ValueError,'external runtime'):
                    verify_package.inspect_zip(damaged,missing_build,supported,None)

if __name__=='__main__':unittest.main()
