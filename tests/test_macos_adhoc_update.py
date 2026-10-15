"""The signed-update tool touches only disposable native bundle fixtures."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import macos_adhoc_update as updater
import player_install as player

sha=lambda data:hashlib.sha256(data).hexdigest()


class AdhocUpdate(unittest.TestCase):
    def snapshot(self,game,new):
        return updater.recovery_folder(game,player.read(new/'manifest.json'))

    def fixture(self,root,external=False):
        game=root/'game';old=root/'old';new=root/'new'
        manifest=dict(format=2,version='old',target_id=player.MACOS,
                      **player.TARGETS[player.MACOS],exe_sha256=sha(b'ORIGINAL EXE'),files=[])
        exe=game/manifest['executable'];exe.parent.mkdir(parents=True);exe.write_bytes(b'ORIGINAL EXE')
        core=game/manifest['data_dir']/'Managed/Assembly-CSharp.dll';core.parent.mkdir(parents=True);core.write_bytes(b'ORIGINAL DLL')
        for name,content,before in [('CW3_Data/Managed/Assembly-CSharp.dll',b'OLD DLL',sha(b'ORIGINAL DLL')),
                                    ('CW3Localization/zh-CN.json',b'TEXT',None)]:
            source=old/name;source.parent.mkdir(parents=True);source.write_bytes(content)
            manifest['files'].append(dict(file=name,before=before,after=sha(content),bytes=len(content)))
        # The real Mac candidate has fourteen files; this test keeps the same
        # shape with distinct permitted sidecars.
        for i in range(12):
            name='CW3_Data/fixture'+str(i);source=old/name;source.parent.mkdir(parents=True,exist_ok=True)
            original=('ORIGINAL '+str(i)).encode();content=('OLD '+str(i)).encode()
            (game/manifest['data_dir']/('fixture'+str(i))).write_bytes(original)
            source.write_bytes(content)
            manifest['files'].append(dict(file=name,before=sha(original),after=sha(content),bytes=len(content)))
        with patch.object(player,'idle'):
            player.install(game,manifest,None,old)
        (old/'manifest.json').write_text(json.dumps(manifest))
        shutil.copytree(old,new)
        fresh=json.loads(json.dumps(manifest));fresh['version']='new'
        changed=new/'CW3_Data/Managed/Assembly-CSharp.dll';changed.write_bytes(b'NEW DLL')
        fresh['files'][0]['after']=sha(b'NEW DLL');fresh['files'][0]['bytes']=len(b'NEW DLL')
        if external:
            added=new/updater.ADDED;added.parent.mkdir(parents=True);added.write_bytes(b'EXTERNAL RUNTIME')
            fresh['files'].append(dict(file=updater.ADDED,before=None,after=sha(b'EXTERNAL RUNTIME'),bytes=len(b'EXTERNAL RUNTIME')))
        (new/'manifest.json').write_text(json.dumps(fresh))
        seal=game/updater.SIGNATURE;seal.parent.mkdir();seal.write_bytes(b'OLD SEAL')
        exe.write_bytes(b'OLD ADHOC EXE')
        return game,old,new,core,exe,seal

    def codesign(self,exe,seal,fail=False):
        def run(command,**kwargs):
            if '--force' in command:
                exe.write_bytes(b'NEW ADHOC EXE');seal.write_bytes(b'NEW SEAL')
                if fail:raise subprocess.CalledProcessError(1,command)
            return subprocess.CompletedProcess(command,0,'','flags=0x2(adhoc)\n')
        return run

    def test_guarded_update_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                self.assertEqual(updater.preflight(game,old,new)[-2],['CW3_Data/Managed/Assembly-CSharp.dll'])
                updater.apply(game,old,new)
                self.assertEqual(core.read_bytes(),b'NEW DLL')
                self.assertEqual(exe.read_bytes(),b'NEW ADHOC EXE')
                state=player.read(game/player.BACKUP/'state.json')
                self.assertEqual(state['adhoc_exe_sha256'],sha(b'NEW ADHOC EXE'))
                updater.recover(game,self.snapshot(game,new))
                self.assertEqual(core.read_bytes(),b'OLD DLL')
                self.assertEqual(exe.read_bytes(),b'OLD ADHOC EXE')
                self.assertEqual(seal.read_bytes(),b'OLD SEAL')
                self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'old')

    def test_sign_failure_restores_old_signed_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal,True)):
                with self.assertRaises(subprocess.CalledProcessError):updater.apply(game,old,new)
            self.assertEqual((core.read_bytes(),exe.read_bytes(),seal.read_bytes()),(b'OLD DLL',b'OLD ADHOC EXE',b'OLD SEAL'))
            self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'old')

    def test_manual_recovery_refuses_unknown_existing_files_without_writes(self):
        for changed in ('core','executable','seal'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                game,old,new,core,exe,seal=self.fixture(Path(directory))
                with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                    updater.apply(game,old,new)
                    target={'core':core,'executable':exe,'seal':seal}[changed]
                    target.write_bytes(b'UNKNOWN USER CHANGE')
                    before={p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()}
                    with self.assertRaisesRegex(RuntimeError,'changed'):
                        updater.recover(game,self.snapshot(game,new))
                    self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()},before)

    def test_manual_recovery_retains_edited_dictionary_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            manifest=player.read(new/'manifest.json');dictionary=new/'CW3Localization/zh-CN.json'
            dictionary.write_bytes(b'NEW TEXT')
            next(row for row in manifest['files'] if row['file']=='CW3Localization/zh-CN.json').update(after=sha(b'NEW TEXT'),bytes=8)
            (new/'manifest.json').write_text(json.dumps(manifest))
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
                dictionary=game/'CW3Localization/zh-CN.json';dictionary.write_bytes(b'USER TRANSLATION')
                folder=self.snapshot(game,new)
                with self.assertRaisesRegex(RuntimeError,'retained'):
                    updater.recover(game,folder)
            self.assertEqual(dictionary.read_bytes(),b'USER TRANSLATION')
            self.assertEqual(core.read_bytes(),b'NEW DLL')
            self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'new')
            self.assertEqual([p.read_bytes() for p in (folder/'user-retained').iterdir()],[b'USER TRANSLATION'])

    def test_interrupted_existing_write_recovers_only_with_its_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            write=player.write_existing;failed=False
            def partial(source,target,metadata):
                nonlocal failed
                if target.resolve()==core.resolve() and not failed:
                    failed=True;target.write_bytes(b'PARTIAL');raise OSError('partial fixture write')
                return write(source,target,metadata)
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                with patch.object(player,'write_existing',side_effect=partial),patch.object(updater,'recover',side_effect=RuntimeError('process ended')):
                    with self.assertRaisesRegex(RuntimeError,'process ended'):updater.apply(game,old,new)
                folder=self.snapshot(game,new)
                self.assertEqual(core.read_bytes(),b'PARTIAL')
                record=player.read(folder/'record.json')
                player.put_json(folder/'record.json',dict(record,phase='ready',in_progress=[]))
                with self.assertRaisesRegex(RuntimeError,'changed'):updater.recover(game,folder)
                self.assertEqual(core.read_bytes(),b'PARTIAL')
                player.put_json(folder/'record.json',record)
                with patch.object(player,'atomic_copy',side_effect=OSError('retention denied')),self.assertRaisesRegex(OSError,'retention denied'):
                    updater.recover(game,folder)
                self.assertEqual(core.read_bytes(),b'PARTIAL')
                failed=False
                with patch.object(player,'write_existing',side_effect=partial),self.assertRaisesRegex(OSError,'partial fixture write'):
                    updater.recover(game,folder)
                self.assertEqual(core.read_bytes(),b'PARTIAL')
                updater.recover(game,folder)
                self.assertIn(b'PARTIAL',[p.read_bytes() for p in (folder/'interrupted-retained').iterdir()])
            self.assertEqual(core.read_bytes(),b'OLD DLL')
            self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'old')

    def test_interrupted_dictionary_edit_is_retained_before_recovery_refuses(self):
        for retention in ('ok','copy_failure','corrupt_copy'):
            with self.subTest(retention=retention),tempfile.TemporaryDirectory() as directory:
                game,old,new,core,exe,seal=self.fixture(Path(directory))
                manifest=player.read(new/'manifest.json')
                (new/'CW3Localization/zh-CN.json').write_bytes(b'NEW TEXT')
                next(row for row in manifest['files'] if row['file']=='CW3Localization/zh-CN.json').update(after=sha(b'NEW TEXT'),bytes=8)
                (new/'manifest.json').write_text(json.dumps(manifest))
                write=player.write_existing
                def interrupted(source,target,metadata):
                    if target.name=='zh-CN.json':
                        target.write_bytes(b'PARTIAL');raise OSError('process ended during dictionary write')
                    return write(source,target,metadata)
                with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                    with patch.object(player,'write_existing',side_effect=interrupted),patch.object(updater,'recover',side_effect=RuntimeError('process ended')):
                        with self.assertRaisesRegex(RuntimeError,'process ended'):updater.apply(game,old,new)
                    dictionary=game/'CW3Localization/zh-CN.json';dictionary.write_bytes(b'USER TRANSLATION')
                    folder=self.snapshot(game,new)
                    before={p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file() and not p.is_relative_to(folder)}
                    def retain(source,target,*args):
                        if retention=='copy_failure':raise OSError('retention denied')
                        target.write_bytes(b'CORRUPT COPY')
                    if retention=='ok':
                        with self.assertRaisesRegex(RuntimeError,'retained'):updater.recover(game,folder)
                        self.assertEqual([p.read_bytes() for p in (folder/'user-retained').iterdir()],[b'USER TRANSLATION'])
                    else:
                        with patch.object(player,'atomic_copy',side_effect=retain),self.assertRaises((OSError,RuntimeError)):
                            updater.recover(game,folder)
                    self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file() and not p.is_relative_to(folder)},before)

    def test_recover_cli_finds_initial_snapshot_by_verified_package(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory),external=True)
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
                # The first bridge candidate used this fixed name; selection must
                # verify its record rather than infer a path from the new version.
                self.snapshot(game,new).rename(game/player.BACKUP/'adhoc-bridge-previous')
                before={p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()}
                wrong=Path(directory)/'wrong';shutil.copytree(new,wrong)
                manifest=player.read(wrong/'manifest.json');manifest['version']='another-version'
                (wrong/'manifest.json').write_text(json.dumps(manifest))
                with patch.object(sys,'argv',['updater','--game',str(game),'--recover','--new-package',str(wrong)]),self.assertRaisesRegex(RuntimeError,'snapshot'):
                    updater.main()
                self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()},before)
                manifest['version']='new'
                (wrong/updater.ADDED).write_bytes(b'WRONG RUNTIME')
                next(row for row in manifest['files'] if row['file']==updater.ADDED).update(after=sha(b'WRONG RUNTIME'),bytes=13)
                (wrong/'manifest.json').write_text(json.dumps(manifest))
                with patch.object(sys,'argv',['updater','--game',str(game),'--recover','--new-package',str(wrong)]),self.assertRaisesRegex(RuntimeError,'snapshot'):
                    updater.main()
                self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()},before)
                with patch.object(sys,'argv',['updater','--game',str(game),'--recover','--new-package',str(new)]):
                    updater.main()
            self.assertEqual((core.read_bytes(),exe.read_bytes(),seal.read_bytes()),(b'OLD DLL',b'OLD ADHOC EXE',b'OLD SEAL'))
            self.assertFalse((game/updater.ADDED).exists())

    def test_existing_applied_snapshot_uses_known_installed_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
                folder=self.snapshot(game,new);record=player.read(folder/'record.json')
                for row in record['files']:row.pop('after_sha256',None)
                player.put_json(folder/'record.json',record)
                updater.recover(game,folder)
            self.assertEqual(core.read_bytes(),b'OLD DLL')
            self.assertEqual(exe.read_bytes(),b'OLD ADHOC EXE')

    def test_added_external_runtime_is_retained_on_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory),external=True)
            external=game/updater.ADDED
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
                self.assertEqual(external.read_bytes(),b'EXTERNAL RUNTIME')
                self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'new')
                updater.recover(game,self.snapshot(game,new))
            self.assertFalse(external.exists())
            self.assertEqual((self.snapshot(game,new)/'added-retained'/updater.ADDED).read_bytes(),b'EXTERNAL RUNTIME')
            self.assertEqual(player.read(game/player.BACKUP/'state.json')['version'],'old')

    def test_sign_failure_with_added_runtime_restores_old_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory),external=True)
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal,True)):
                with self.assertRaises(subprocess.CalledProcessError):updater.apply(game,old,new)
            self.assertFalse((game/updater.ADDED).exists())
            self.assertEqual((core.read_bytes(),exe.read_bytes(),seal.read_bytes()),(b'OLD DLL',b'OLD ADHOC EXE',b'OLD SEAL'))

    def test_external_runtime_update_keeps_bundle_bytes_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,old,new,core,exe,seal=self.fixture(root,external=True)
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
            before={p.relative_to(game).as_posix():(player.digest(p),player.metadata(p)) for p in (game/'CW3.app').rglob('*') if p.is_file()}
            next_package=root/'next';shutil.copytree(new,next_package)
            fresh=player.read(next_package/'manifest.json');fresh['version']='external-next'
            (next_package/updater.ADDED).write_bytes(b'UPDATED EXTERNAL RUNTIME')
            row=next(row for row in fresh['files'] if row['file']==updater.ADDED)
            row.update(after=sha(b'UPDATED EXTERNAL RUNTIME'),bytes=len(b'UPDATED EXTERNAL RUNTIME'))
            (next_package/'manifest.json').write_text(json.dumps(fresh))
            def verify_only(command,**kwargs):
                self.assertNotIn('--force',command,'An external-only update must not re-sign')
                return subprocess.CompletedProcess(command,0,'','flags=0x2(adhoc)\n')
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=verify_only):
                updater.apply(game,new,next_package)
                self.assertEqual((game/updater.ADDED).read_bytes(),b'UPDATED EXTERNAL RUNTIME')
                after={p.relative_to(game).as_posix():(player.digest(p),player.metadata(p)) for p in (game/'CW3.app').rglob('*') if p.is_file()}
                self.assertEqual(before,after)
                updater.recover(game,updater.recovery_folder(game,fresh))
            self.assertEqual((game/updater.ADDED).read_bytes(),b'EXTERNAL RUNTIME')

    def test_followup_bridge_fix_retains_initial_recovery_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,old,new,core,exe,seal=self.fixture(root,external=True)
            with patch.object(player,'idle'),patch.object(updater.subprocess,'run',side_effect=self.codesign(exe,seal)):
                updater.apply(game,old,new)
                initial=(self.snapshot(game,new)/'record.json').read_bytes()
                fixed=root/'fixed';shutil.copytree(new,fixed)
                manifest=player.read(fixed/'manifest.json');manifest['version']='bridge-fix'
                (fixed/'CW3_Data/Managed/Assembly-CSharp.dll').write_bytes(b'FIXED DLL')
                manifest['files'][0].update(after=sha(b'FIXED DLL'),bytes=len(b'FIXED DLL'))
                (fixed/'manifest.json').write_text(json.dumps(manifest))
                updater.apply(game,new,fixed)
                self.assertEqual(core.read_bytes(),b'FIXED DLL')
                self.assertEqual((self.snapshot(game,new)/'record.json').read_bytes(),initial)
                updater.recover(game,updater.recovery_folder(game,manifest))
                self.assertEqual(core.read_bytes(),b'NEW DLL')

    def test_signature_and_package_mismatch_fail_before_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            game,old,new,core,exe,seal=self.fixture(Path(directory))
            with patch.object(updater.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','flags=0x0(none)')):
                with self.assertRaisesRegex(RuntimeError,'ad-hoc'):updater.preflight(game,old,new)
            self.assertFalse((self.snapshot(game,new)).exists())
            fresh=player.read(new/'manifest.json');fresh['files'][0]['before']=sha(b'OTHER')
            (new/'manifest.json').write_text(json.dumps(fresh))
            with self.assertRaisesRegex(RuntimeError,'original bases'):updater.preflight(game,old,new)
            self.assertFalse((self.snapshot(game,new)).exists())


if __name__=='__main__':unittest.main()
