"""Real file operations for the new package; mock only the global process-idle boundary."""
from pathlib import Path
import hashlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import player_install as player
sha=lambda b:hashlib.sha256(b).hexdigest()
class PlayerPayload(unittest.TestCase):
    def fixture(self,root):
        game=root/'game';package=root/'package';(game/'CW3_Data').mkdir(parents=True)
        (game/'CW3_Data/core').write_bytes(b'original');(game/'save.sentinel').write_bytes(b'keep')
        files={'CW3_Data/core':b'patched','CW3Localization/zh-CN.json':b'shipped dictionary'}
        rows=[]
        for name,data in files.items():
            p=package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            rows.append(dict(file=name,before=sha(b'original')if name.endswith('core')else None,after=sha(data),bytes=len(data)))
        return game,package,dict(format=2,version='fixture',files=rows,runtime_files=['CW3Localization/zh-CN.json'])
    @patch.object(player,'idle')
    def test_complete_file_install_and_custom_dictionary_restore(self,_):
        with tempfile.TemporaryDirectory()as name:
            game,package,manifest=self.fixture(Path(name));player.install(game,manifest,None,package)
            self.assertEqual((game/'CW3_Data/core').read_bytes(),b'patched')
            state=player.backup_info(game);self.assertEqual(player.status(game,manifest,state),'installed')
            dictionary=game/'CW3Localization/zh-CN.json';dictionary.write_bytes(b'user dictionary')
            state=player.preserve_runtime_updates(game,state,manifest);player.restore(game,state)
            self.assertEqual((game/'CW3_Data/core').read_bytes(),b'original');self.assertFalse(dictionary.exists())
            saved=list((game/player.BACKUP/'runtime-updates').iterdir());self.assertEqual([p.read_bytes()for p in saved],[b'user dictionary'])
            self.assertEqual((game/'save.sentinel').read_bytes(),b'keep')
    @patch.object(player,'idle')
    def test_damaged_payload_refused_before_any_game_write(self,_):
        with tempfile.TemporaryDirectory()as name:
            game,package,manifest=self.fixture(Path(name));(package/'CW3Localization/zh-CN.json').write_bytes(b'broken')
            with self.assertRaisesRegex(RuntimeError,'安装包损坏'):player.install(game,manifest,None,package)
            self.assertEqual((game/'CW3_Data/core').read_bytes(),b'original');self.assertFalse((game/player.BACKUP).exists())
            self.assertEqual((game/'save.sentinel').read_bytes(),b'keep')
    @patch.object(player,'idle')
    def test_interrupted_second_file_rolls_back_first_file(self,_):
        with tempfile.TemporaryDirectory()as name:
            game,package,manifest=self.fixture(Path(name));replace=player.os.replace;failed=False
            def fail_once(source,target):
                nonlocal failed
                if Path(target)==game/'CW3Localization/zh-CN.json' and not failed:
                    failed=True;raise OSError('simulated filesystem failure')
                return replace(source,target)
            with patch.object(player.os,'replace',side_effect=fail_once):
                with self.assertRaisesRegex(OSError,'filesystem failure'):player.install(game,manifest,None,package)
            self.assertTrue(failed);self.assertEqual((game/'CW3_Data/core').read_bytes(),b'original')
            self.assertFalse((game/'CW3Localization/zh-CN.json').exists());self.assertFalse((game/player.BACKUP/'journal.json').exists())
            self.assertEqual((game/'save.sentinel').read_bytes(),b'keep')

    def next_package(self,package,manifest):
        import copy
        updated=copy.deepcopy(manifest)
        for row in updated['files']:
            content=b'next core' if row['file'].endswith('core') else b'next dictionary'
            (package/row['file']).write_bytes(content)
            row.update(after=sha(content),bytes=len(content))
        return updated

    def test_unknown_missing_and_unmanaged_combinations_refuse_install_without_writes(self):
        for kind in ('unknown','missing','unmanaged'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                game,package,manifest=self.fixture(Path(folder));core=game/'CW3_Data/core'
                if kind=='missing':core.unlink()
                elif kind=='unknown':core.write_bytes(b'other mod')
                else:
                    core.write_bytes(b'patched');dictionary=game/'CW3Localization/zh-CN.json';dictionary.parent.mkdir();dictionary.write_bytes(b'shipped dictionary')
                # A retired metadata field cannot turn unknown files into an accepted state.
                manifest['legacy_hashes']={row['file']:player.digest(game/row['file']) for row in manifest['files']}
                expected='unmanaged' if kind=='unmanaged' else 'unknown'
                self.assertEqual(player.status(game,manifest,None),expected)
                before={p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()}
                with self.assertRaises(RuntimeError):player.install(game,manifest,None,package)
                self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()},before)
                self.assertFalse((game/player.BACKUP).exists())

    @patch.object(player,'idle')
    def test_restore_refuses_unknown_core_and_keeps_backup_and_user_files(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=self.fixture(Path(folder));player.install(game,manifest,None,package)
            state=player.backup_info(game);(game/'CW3_Data/core').write_bytes(b'other mod')
            before={p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(RuntimeError,'文件已被其他程序修改'):player.restore(game,state)
            self.assertEqual({p.relative_to(game):p.read_bytes() for p in game.rglob('*') if p.is_file()},before)
            self.assertFalse((game/player.BACKUP/'journal.json').exists())

    @patch.object(player,'idle')
    def test_fixed_temporary_links_and_files_are_never_used_or_removed(self,_):
        for kind in ('file','link','dangling'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);game,package,manifest=self.fixture(root)
                outside=root/'outside'
                if kind!='dangling':outside.write_bytes(b'USER FILE')
                collision=game/'CW3_Data/core.cw3-install-tmp'
                if kind=='file':collision.write_bytes(b'USER FILE')
                else:collision.symlink_to(outside)
                player.install(game,manifest,None,package)
                backup=game/player.BACKUP
                for name in ('state.tmp','journal.tmp'):
                    if kind=='file':(backup/name).write_bytes(b'USER FILE')
                    else:(backup/name).symlink_to(outside)
                (game/'CW3Localization/zh-CN.json').write_bytes(b'user dictionary')
                state=player.preserve_runtime_updates(game,player.backup_info(game),manifest)
                # Exercise interrupted restore too: old fixed names are not owned
                # by this invocation, even when a journal exists.
                player.put_json(backup/'journal.json',dict(action='install',files=manifest['files']))
                player.restore(game,state)
                self.assertEqual((game/'CW3_Data/core').read_bytes(),b'original')
                self.assertFalse((game/'CW3_Data/core').is_symlink())
                self.assertFalse((backup/'state.json').is_symlink())
                self.assertEqual(player.read(backup/'state.json')['files'],state['files'])
                for path in (collision,backup/'state.tmp',backup/'journal.tmp'):
                    if kind=='file':self.assertEqual(path.read_bytes(),b'USER FILE')
                    else:self.assertTrue(path.is_symlink());self.assertEqual(path.readlink(),outside)
                if kind=='dangling':self.assertFalse(outside.exists())
                else:self.assertEqual(outside.read_bytes(),b'USER FILE')
                self.assertIn(b'user dictionary',[p.read_bytes() for p in (backup/'runtime-updates').iterdir()])
                self.assertEqual((game/'save.sentinel').read_bytes(),b'keep')

    def test_failed_atomic_writes_preserve_target_and_remove_only_owned_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.write_bytes(b'new')
            target=root/'state.json';target.write_bytes(b'old')
            for write in (lambda:player.put_json(target,dict(value='new')),lambda:player.atomic_copy(source,target)):
                with patch.object(player.os,'replace',side_effect=OSError('replace failed')):
                    with self.assertRaisesRegex(OSError,'replace failed'):write()
                self.assertEqual(target.read_bytes(),b'old')
                self.assertEqual({p.name for p in root.iterdir()},{'source','state.json'})

    @patch.object(player,'idle')
    def test_missing_settings_use_runtime_defaults_without_installing_a_template(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=self.fixture(Path(folder))
            player.install(game,manifest,None,package)
            self.assertFalse((game/'CW3Localization/text-style.json').exists())
            player.restore(game,player.backup_info(game))
            self.assertFalse((game/'CW3Localization/text-style.json').exists())

    @patch.object(player,'idle')
    def test_upgrade_preserves_saved_defaults_custom_settings_and_bad_config_bytes(self,_):
        cases=[b'{"format":1,"roles":{}}\n',
               '{"format":1,"roles":{"body":{"font":"我的字体.ttf","size_percent":125}}}\n'.encode(),
               b'invalid configuration']
        for text in cases:
            with self.subTest(text=text),tempfile.TemporaryDirectory() as folder:
                game,package,manifest=self.fixture(Path(folder));player.install(game,manifest,None,package)
                style=game/'CW3Localization/text-style.json';style.write_bytes(text)
                font=game/'CW3Localization/fonts/User.ttf';font.parent.mkdir();font.write_bytes(b'USER FONT')
                dictionary=game/'CW3Localization/zh-CN.json';dictionary.write_bytes(b'user translation')
                updated=self.next_package(package,manifest)
                player.install(game,updated,player.backup_info(game),package)
                self.assertEqual(dictionary.read_bytes(),b'next dictionary')
                self.assertEqual(style.read_bytes(),text);self.assertEqual(font.read_bytes(),b'USER FONT')
                history=game/player.BACKUP/'runtime-updates'
                self.assertIn(b'user translation',[p.read_bytes() for p in history.iterdir()])
                player.restore(game,player.backup_info(game))
                self.assertEqual(style.read_bytes(),text);self.assertEqual(font.read_bytes(),b'USER FONT')

    @patch.object(player,'idle')
    def test_legacy_template_ownership_is_removed_on_upgrade_and_config_survives_restore(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=self.fixture(Path(folder));player.install(game,manifest,None,package)
            state=player.backup_info(game)
            style=game/'CW3Localization/text-style.json';style.write_bytes(b'{\n  "format":1,"roles":{}\n}\n')
            state['files'].append(dict(file='CW3Localization/text-style.json',before=None,after=player.digest(style),bytes=style.stat().st_size))
            player.put_json(game/player.BACKUP/'state.json',state)
            # The settings menu rewrites even an unchanged selection as compact JSON.
            style.write_bytes(b'{"format":1,"roles":{}}\n');saved=style.read_bytes()
            updated=self.next_package(package,manifest)
            player.install(game,updated,player.backup_info(game),package)
            state=player.backup_info(game)
            self.assertNotIn('CW3Localization/text-style.json',{r['file'] for r in state['files']})
            self.assertEqual(style.read_bytes(),saved)
            player.restore(game,state)
            self.assertEqual(style.read_bytes(),saved)

    @patch.object(player,'idle')
    def test_failed_upgrade_keeps_settings_and_custom_font_during_original_rollback(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=self.fixture(Path(folder));player.install(game,manifest,None,package)
            style=game/'CW3Localization/text-style.json';style.write_bytes(b'legacy template')
            state=player.backup_info(game);state['files'].append(dict(file='CW3Localization/text-style.json',before=None,after=player.digest(style),bytes=15))
            player.put_json(game/player.BACKUP/'state.json',state);style.write_bytes(b'USER SETTINGS')
            font=game/'CW3Localization/fonts/Own.otf';font.parent.mkdir();font.write_bytes(b'USER FONT')
            updated=self.next_package(package,manifest);replace=player.os.replace;failed=False
            def fail_once(source,target):
                nonlocal failed
                if Path(target)==game/'CW3Localization/zh-CN.json' and not failed:
                    failed=True;raise OSError('upgrade write failure')
                return replace(source,target)
            with patch.object(player.os,'replace',side_effect=fail_once),self.assertRaisesRegex(OSError,'upgrade write failure'):
                player.install(game,updated,player.backup_info(game),package)
            self.assertEqual((game/'CW3_Data/core').read_bytes(),b'original')
            self.assertEqual(style.read_bytes(),b'USER SETTINGS');self.assertEqual(font.read_bytes(),b'USER FONT')
            self.assertFalse((game/player.BACKUP/'journal.json').exists())

    @patch.object(player,'idle')
    def test_controlled_fonts_are_hash_locked_before_upgrade(self,_):
        for changed in ('font.ttf','serif.ttf'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as folder:
                game,package,manifest=self.fixture(Path(folder))
                for name in ('font.ttf','serif.ttf'):
                    file='CW3Localization/'+name;target=package/file;target.write_bytes(b'CONTROLLED FONT')
                    manifest['files'].append(dict(file=file,before=None,after=sha(b'CONTROLLED FONT'),bytes=15))
                player.install(game,manifest,None,package)
                (game/'CW3Localization'/changed).write_bytes(b'OTHER FONT')
                with self.assertRaisesRegex(RuntimeError,'版本不匹配'):
                    player.install(game,manifest,player.backup_info(game),package)
                self.assertEqual((game/'CW3_Data/core').read_bytes(),b'patched')
                self.assertFalse((game/player.BACKUP/'runtime-updates').exists())



    @patch.object(player,'idle')
    def test_restoring_legacy_backup_keeps_user_settings_before_reinstall(self,_):
        with tempfile.TemporaryDirectory() as folder:
            game,package,manifest=self.fixture(Path(folder));player.install(game,manifest,None,package)
            style=game/'CW3Localization/text-style.json';style.write_bytes(b'legacy template')
            state=player.backup_info(game);state['files'].append(dict(file='CW3Localization/text-style.json',before=None,after=player.digest(style),bytes=15))
            player.put_json(game/player.BACKUP/'state.json',state)
            style.write_bytes(b'USER SETTINGS')
            legacy=dict(manifest,files=state['files'])
            state=player.preserve_runtime_updates(game,state,legacy);player.restore(game,state)
            self.assertEqual(style.read_bytes(),b'USER SETTINGS')
            player.install(game,manifest,player.backup_info(game),package)
            self.assertEqual(style.read_bytes(),b'USER SETTINGS')

if __name__=='__main__':unittest.main()
