"""Styles stay bounded and install recovery retains mutable config without widening paths."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import text_style
import player_install

class TextStyleFiles(unittest.TestCase):
    def test_defaults_and_generic_pixel_config(self):
        root=Path(__file__).resolve().parents[1]
        default=text_style.validate_style(root/'resources/text-style.json')
        self.assertTrue(all(r=={'font':'sans','size_percent':100} for r in default['roles'].values()))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'style.json'
            value={'format':1,'roles':{'ui':{'font':'pixel.ttf','size_percent':100,'pixel_size':8}}}
            path.write_text(json.dumps(value))
            self.assertEqual(text_style.validate_style(path),value)

    def test_local_filenames_and_sampling_do_not_require_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'style.json'
            for font in ('文楷.ttf','Local Serif.OTF'):
                value={'format':1,'roles':{'body':{'font':font,'size_percent':100,'pixel_size':0}}}
                path.write_text(json.dumps(value))
                self.assertEqual(text_style.validate_style(path,{'sans','serif'}),value)
            for font in ('../font.ttf','C:\\font.ttf','a/b.otf','.hidden.ttf','font\x7f.ttf'):
                value['roles']['body']['font']=font;path.write_text(json.dumps(value))
                with self.subTest(font=font),self.assertRaises(ValueError):text_style.validate_style(path)
            value['roles']['body']['font']='font.ttf'
            for pixel in (True,-1,65):
                value['roles']['body']['pixel_size']=pixel;path.write_text(json.dumps(value))
                with self.subTest(pixel=pixel),self.assertRaises(ValueError):text_style.validate_style(path)

    def test_every_display_role_accepts_registered_custom_faces(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'style.json'
            for font in ('sans','serif','pixel_custom','my_font'):
                value={'format':1,'roles':{role:{'font':font,'size_percent':100} for role in text_style.ROLES}}
                path.write_text(json.dumps(value))
                self.assertEqual(text_style.validate_style(path,{font}),value)
                with self.assertRaises(ValueError):text_style.validate_style(path,{'unrelated'})

    def test_invalid_configuration_rejected_before_update(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'style.json'
            cases=[{'format':True,'roles':{}},{'format':1,'roles':{'code_input':{'font':'sans','size_percent':100}}},
                   {'format':1,'roles':{'body':{'font':'../font','size_percent':100}}},
                   {'format':1,'roles':{'ui':{'font':'serif','size_percent':True}}},
                   {'format':1,'roles':{'ui':{'font':'serif','size_percent':151}}},
                   {'format':1,'roles':{},'file':'../font.ttf'}]
            for case in cases:
                path.write_text(json.dumps(case))
                with self.subTest(case=case),self.assertRaises(ValueError):text_style.validate_style(path)
            path.write_text(' '*32769)
            with self.assertRaises(ValueError):text_style.validate_style(path)

    def test_exact_style_paths_and_restore_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);name='CW3Localization/text-style.json';path=player_install.safe(game,name);path.parent.mkdir();path.write_bytes(b'custom style')
            row={'file':name,'before':None,'after':player_install.digest(path),'bytes':path.stat().st_size}
            state={'install_root':str(game.resolve()),'files':[row]};manifest={'files':[row],'runtime_files':[name]}
            path.write_bytes(b'changed local style')
            self.assertEqual(player_install.status(game,manifest,state),'customized')
            (game/player_install.BACKUP).mkdir()
            with patch.object(player_install,'idle'):updated=player_install.preserve_runtime_updates(game,state,manifest)
            self.assertEqual(updated['files'][0]['after'],player_install.digest(path))
            for other in ('CW3Localization/anything.ttf','CW3Localization/zpix.ttf','CW3Localization/../bad'):
                with self.assertRaises(ValueError):player_install.safe(game,other)

if __name__=='__main__':unittest.main()
