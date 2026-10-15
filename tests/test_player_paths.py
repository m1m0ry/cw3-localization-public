from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import player_install as player

class PlayerPaths(unittest.TestCase):
    layout=dict(target_id=player.WINDOWS,**player.TARGETS[player.WINDOWS])
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
            player.ensure_writable(game,[{'file':player.DEFAULT_DICTIONARY,'before':None}],0,self.layout)
            self.assertFalse((game/'CW3Localization').exists())

    def test_low_space_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            with patch.object(player.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
                with self.assertRaisesRegex(RuntimeError,'空间不足'):player.ensure_writable(root,[],1,self.layout)
            self.assertEqual(list(root.iterdir()),[])

    def test_read_only_game_file_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);data=root/'CW3_Data';data.mkdir();file=data/'level1';file.write_bytes(b'original');file.chmod(0o444)
            try:
                if os.access(file,os.W_OK):self.skipTest('Current filesystem/user bypasses read-only mode')
                with self.assertRaisesRegex(RuntimeError,'文件不可写'):player.ensure_writable(root,[{'file':'CW3_Data/level1'}],0,self.layout)
                self.assertEqual(file.read_bytes(),b'original')
            finally:file.chmod(0o644)

if __name__=='__main__':unittest.main()
