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
if __name__=='__main__':unittest.main()
