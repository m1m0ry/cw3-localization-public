"""Complete package reinstall replaces rollback and version-history inference."""
from pathlib import Path
import json,shutil,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import player_install as player
from player_fixture import fixture,sha,snapshot

class CompleteInstall(unittest.TestCase):
    def setUp(self):
        guard=patch.dict(player.FINGERPRINTS,{player.WINDOWS:sha(b'EXE')});guard.start();self.addCleanup(guard.stop)
        idle=patch.object(player,'idle');idle.start();self.addCleanup(idle.stop)

    def test_first_repeat_upgrade_and_downgrade_preserve_user_data(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder));player.install(game,manifest,package)
            user=game/'CW3Localization';(user/'zh-CN.json').write_bytes(b'USER TRANSLATION');(user/'text-style.json').write_bytes(b'INVALID USER CONFIG')
            (user/'fonts').mkdir();(user/'fonts/custom.ttf').write_bytes(b'USER FONT')
            backup=game/'.cw3-zh-backup';backup.mkdir();(backup/'journal.json').write_bytes(b'OLD INCOMPLETE DATA')
            preserved={name:(game/name).read_bytes() for name in ('CW3Localization/zh-CN.json','CW3Localization/text-style.json','CW3Localization/fonts/custom.ttf','.cw3-zh-backup/journal.json','save.sentinel')}
            newer=Path(folder)/'newer';shutil.copytree(package,newer);updated=json.loads(json.dumps(manifest));updated['version']='two'
            for row in updated['files']:
                if row['file'] in player.RUNTIME:continue
                path=newer/row['file'];path.write_bytes(b'NEW PROGRAM');row.update(after=sha(b'NEW PROGRAM'),bytes=11)
            for source,doc in ((package,manifest),(newer,updated),(newer,updated),(package,manifest)):
                player.install(game,doc,source)
                for row in doc['files']:
                    if row['file'] not in player.RUNTIME:self.assertEqual(player.digest(player.installed_path(game,row['file'],doc)),row['after'])
                for name,content in preserved.items():self.assertEqual((game/name).read_bytes(),content)

    def test_cli_selects_old_complete_package_without_overwriting_legacy_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder))
            name='CW3Localization/text-style.json';(package/name).write_bytes(b'LEGACY DEFAULT')
            manifest['files'].append(dict(file=name,before=None,after=sha(b'LEGACY DEFAULT'),bytes=14))
            (package/'manifest.json').write_text(json.dumps(manifest))
            target=game/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'USER SETTINGS')
            with patch.object(sys,'argv',['install','--package',str(package),'--game',str(game),'--action','install']):player.main()
            self.assertEqual(target.read_bytes(),b'USER SETTINGS')

    def test_interruption_is_repaired_by_reapplying_without_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder));copy=player.atomic_copy
            def fail(source,target,*args,**kwargs):
                if target==game/'CW3_Data/level2':raise OSError('write interrupted')
                return copy(source,target,*args,**kwargs)
            with patch.object(player,'atomic_copy',side_effect=fail),self.assertRaisesRegex(OSError,'interrupted'):player.install(game,manifest,package)
            core=game/'CW3_Data/Managed/Assembly-CSharp.dll'
            self.assertEqual(player.digest(core),next(r['after'] for r in manifest['files'] if r['file']=='CW3_Data/Managed/Assembly-CSharp.dll'))
            self.assertFalse((game/'.cw3-zh-backup').exists())
            player.install(game,manifest,package)
            for row in manifest['files']:self.assertEqual(player.digest(player.installed_path(game,row['file'],manifest)),row['after'])

    def test_bad_incomplete_or_extra_payload_is_refused_before_any_write(self):
        for kind in ('hash','missing','extra','target','anchor'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                game,package,manifest=fixture(Path(folder))
                if kind=='hash':(package/manifest['files'][-1]['file']).write_bytes(b'BROKEN')
                elif kind=='missing':manifest['files'].pop()
                elif kind=='extra':manifest['files'].append(dict(file='CW3_Data/arbitrary',after='0'*64,bytes=1))
                elif kind=='target':manifest['platform']=2
                else:(game/'CW3_Data/anchor').write_bytes(b'OTHER BUILD')
                before=snapshot(game)
                with self.assertRaises((ValueError,RuntimeError)):player.install(game,manifest,package)
                self.assertEqual(snapshot(game),before)

    def test_cleanup_removes_only_injected_programs_and_requires_steam_for_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder));player.install(game,manifest,package)
            keep=game/'CW3Localization/zh-CN.json';keep.write_bytes(b'USER DICTIONARY')
            unknown=game/'CW3_Data/Managed/AnotherMod.dll';unknown.write_bytes(b'OTHER MOD')
            backup=game/'.cw3-zh-backup';backup.mkdir();(backup/'original').write_bytes(b'UNIQUE BACKUP')
            for name in player.INJECTED:
                path=player.installed_path(game,name,manifest);path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists():path.write_bytes(b'OLD HELPER')
            core=game/'CW3_Data/Managed/Assembly-CSharp.dll';patched=core.read_bytes()
            player.clean(game,manifest);player.clean(game,manifest)
            self.assertTrue(all(not player.installed_path(game,n,manifest).exists() for n in player.INJECTED))
            self.assertEqual(core.read_bytes(),patched)  # Steam verification is still required.
            self.assertEqual(keep.read_bytes(),b'USER DICTIONARY');self.assertEqual(unknown.read_bytes(),b'OTHER MOD');self.assertEqual((backup/'original').read_bytes(),b'UNIQUE BACKUP')

    def test_obsolete_helpers_are_removed_but_unknown_files_remain(self):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=fixture(Path(folder));stale=game/'CW3_Data/Managed/CW3Display.dll';stale.write_bytes(b'OBSOLETE')
            other=stale.with_name('User.dll');other.write_bytes(b'KEEP')
            player.install(game,manifest,package);self.assertFalse(stale.exists());self.assertEqual(other.read_bytes(),b'KEEP')

    def test_dictionary_appearing_during_seed_commit_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'seed';source.write_bytes(b'OFFICIAL');target=root/'zh-CN.json';link=player.os.link
            def race(temp,destination):
                destination.write_bytes(b'USER CREATED');return link(temp,destination)
            with patch.object(player.os,'link',side_effect=race):player.atomic_copy(source,target,create_only=True)
            self.assertEqual(target.read_bytes(),b'USER CREATED');self.assertEqual(set(p.name for p in root.iterdir()),{'seed','zh-CN.json'})

    def test_failed_atomic_write_keeps_target_and_cleans_its_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.write_bytes(b'NEW');target=root/'target';target.write_bytes(b'OLD')
            with patch.object(player.os,'replace',side_effect=OSError('failed')),self.assertRaises(OSError):player.atomic_copy(source,target)
            self.assertEqual(target.read_bytes(),b'OLD');self.assertEqual(set(p.name for p in root.iterdir()),{'source','target'})
if __name__=='__main__':unittest.main()
