from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import player_install as player

class PlayerPaths(unittest.TestCase):
    def test_windows_multi_library_unicode_and_spaces(self):
        vdf=r'''"libraryfolders" { "0" { "path" "C:\\Program Files (x86)\\Steam" } "1" { "path" "D:\\游戏 库 & Mods" } }'''
        self.assertEqual(player.library_paths(vdf),[r'C:\Program Files (x86)\Steam',r'D:\游戏 库 & Mods'])
        self.assertEqual(player.library_paths(r'"1" "E:\\SteamLibrary"'),[r'E:\SteamLibrary'])

    def test_crossover_drive_mapping_uses_selected_bottle(self):
        bottle=Path('/tmp/自选 Bottle')
        self.assertEqual(player.bottle_path(r'C:\Program Files (x86)\Steam',bottle),bottle/'drive_c/Program Files (x86)/Steam')
        self.assertEqual(player.bottle_path(r'D:\游戏 库',bottle),bottle/'dosdevices/d:/游戏 库')

    def test_game_file_must_stay_inside_selected_directory(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);game=root/'游戏 with spaces';game.mkdir();outside=root/'outside';outside.mkdir()
            for path in ('../outside','/tmp/CW3_Data/file','CW3_Data/../../outside'):
                with self.subTest(path=path),self.assertRaises(ValueError):player.safe(game,path)
            (game/'CW3_Data').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):player.safe(game,'CW3_Data/level1')

    def test_external_paths_are_exact_and_new_directory_is_preflighted(self):
        with tempfile.TemporaryDirectory() as name:
            game=Path(name)
            self.assertEqual(player.safe(game,'CW3Localization/zh-CN.json'),game/'CW3Localization/zh-CN.json')
            for file in ('CW3Localization/other.json','CW3Localization/../outside','other/font.ttf'):
                with self.assertRaises(ValueError):player.safe(game,file)
            player.ensure_writable(game,[{'file':'CW3Localization/zh-CN.json','before':None}],0)
            self.assertFalse((game/'CW3Localization').exists())

    def test_custom_dictionary_is_preserved_before_restore_but_core_changes_are_refused(self):
        import hashlib
        with tempfile.TemporaryDirectory() as name:
            game=Path(name);data=game/'CW3_Data';data.mkdir();core=data/'level1';core.write_bytes(b'patched')
            external=game/'CW3Localization';external.mkdir();dictionary=external/'zh-CN.json';dictionary.write_bytes(b'user edited dictionary')
            backup=game/player.BACKUP;original=backup/'original/CW3_Data';original.mkdir(parents=True);(original/'level1').write_bytes(b'original')
            sha=lambda b:hashlib.sha256(b).hexdigest()
            rows=[{'file':'CW3_Data/level1','before':sha(b'original'),'after':sha(b'patched'),'bytes':7},{'file':'CW3Localization/zh-CN.json','before':None,'after':sha(b'shipped dictionary'),'bytes':18}]
            state={'format':1,'install_root':str(game.resolve()),'version':'v12','files':rows};player.put_json(backup/'state.json',state)
            manifest={'files':rows,'runtime_files':['CW3Localization/zh-CN.json']}
            self.assertEqual(player.status(game,manifest,state),'customized')
            core.write_bytes(b'other mod')
            self.assertEqual(player.status(game,manifest,state),'unknown')
            self.assertEqual(player.preserve_runtime_updates(game,state,manifest),state)
            self.assertFalse((backup/'runtime-updates').exists())
            core.write_bytes(b'patched')
            with patch.object(player,'idle'):
                updated=player.preserve_runtime_updates(game,state,manifest)
                player.restore(game,updated)
            saved=list((backup/'runtime-updates').iterdir())
            self.assertEqual([p.read_bytes() for p in saved],[b'user edited dictionary'])
            self.assertEqual(core.read_bytes(),b'original')
            self.assertFalse(dictionary.exists())
            self.assertFalse((backup/'journal.json').exists())

    def test_low_space_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            with patch.object(player.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
                with self.assertRaisesRegex(RuntimeError,'空间不足'):player.ensure_writable(root,[],1)
            self.assertEqual(list(root.iterdir()),[])

    def test_read_only_game_file_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);data=root/'CW3_Data';data.mkdir();file=data/'level1';file.write_bytes(b'original');file.chmod(0o444)
            try:
                if os.access(file,os.W_OK):self.skipTest('Current filesystem/user bypasses read-only mode')
                with self.assertRaisesRegex(RuntimeError,'文件不可写'):player.ensure_writable(root,[{'file':'CW3_Data/level1'}],0)
                self.assertEqual(file.read_bytes(),b'original')
            finally:file.chmod(0o644)

    def test_backup_is_bound_to_installation(self):
        with tempfile.TemporaryDirectory() as name:
            game=Path(name);backup=game/player.BACKUP;backup.mkdir()
            player.put_json(backup/'state.json',{'install_root':str(game/'different installation'),'files':[]})
            with self.assertRaisesRegex(RuntimeError,'另一安装位置'):player.backup_info(game)


class SlimOriginalGuards(unittest.TestCase):
    def test_old_omitted_resource_is_rejected_without_writes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            game=Path(folder);data=game/'CW3_Data';data.mkdir()
            target=data/'kept';target.write_bytes(b'original kept')
            omitted=data/'omitted';omitted.write_bytes(b'old serialized resource')
            sha=lambda b:hashlib.sha256(b).hexdigest()
            row=dict(file='CW3_Data/kept',before=sha(b'original kept'),after=sha(b'new patch'),bytes=9)
            manifest=dict(files=[row],required_originals={'CW3_Data/omitted':sha(b'original omitted')})
            before={p.name:p.read_bytes() for p in data.iterdir()}
            self.assertEqual(player.status(game,manifest,None),'unknown')
            with self.assertRaisesRegex(RuntimeError,'旧补丁'):
                player.install(game,manifest,None)
            self.assertEqual({p.name:p.read_bytes() for p in data.iterdir()},before)
            self.assertFalse((game/player.BACKUP).exists())
            omitted.write_bytes(b'original omitted')
            self.assertEqual(player.status(game,manifest,None),'original')
            target.write_bytes(b'new patch')
            self.assertEqual(player.status(game,manifest,{'files':[row]}),'installed')
            omitted.write_bytes(b'old serialized resource')
            self.assertEqual(player.status(game,manifest,{'files':[row]}),'unknown')

if __name__=='__main__':unittest.main()
