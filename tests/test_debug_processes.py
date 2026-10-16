"""Debug enable/disable use host process queries before changing fixture game files."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import player_install as player


class DebugProcesses(unittest.TestCase):
    def fixture(self,root,mode):
        game=root/'游戏 with spaces';managed=game/'CW3_Data/Managed';managed.mkdir(parents=True)
        build=root/'debug';build.mkdir();base=b'base core';debug=b'debug core';helper=b'debug helper'
        digest=lambda data:hashlib.sha256(data).hexdigest()
        (build/'base.dll').write_bytes(base);(build/'Assembly-CSharp.debug.dll').write_bytes(debug);(build/'CW3Debug.dll').write_bytes(helper)
        manifest=dict(base=str(build/'base.dll'),base_sha256=digest(base),debug_sha256=digest(debug),helper_sha256=digest(helper))
        (build/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
        (managed/'Assembly-CSharp.dll').write_bytes(base if mode=='enable' else debug)
        (game/'keep.txt').write_bytes(b'unrelated file')
        if mode=='disable':
            (managed/'CW3Debug.dll').write_bytes(helper);state=game/'CW3_Data/cw3-debug';state.mkdir()
            (state/'enabled.txt').write_text(manifest['debug_sha256'],encoding='utf8')
        config=root/'config.json';config.write_text(json.dumps(dict(target_id=player.WINDOWS,game=str(game))),encoding='utf8')
        return config,build,game

    def snapshot(self,game):
        return {p.relative_to(game).as_posix():p.read_bytes() for p in game.rglob('*') if p.is_file()}

    def invoke(self,host,mode,config,build,processes='',error=None):
        def query(command,**kwargs):
            # These are the OS query protocols; no real process is queried or controlled.
            if host=='win32':self.assertEqual(command,['tasklist','/FI','IMAGENAME eq CW3.exe','/FO','CSV','/NH'])
            else:self.assertEqual((Path(command[0]).name,command[1]),('pgrep','-fl'))
            if error=='missing':raise FileNotFoundError('process query unavailable')
            code=2 if error else 0 if host=='win32' or re.search(command[2],processes) else 1
            result=subprocess.CompletedProcess(command,code,processes,'query failed' if error else '')
            if kwargs.get('check'):result.check_returncode()
            return result
        args=['debug.py','--config',str(config),'--debug-build',str(build),mode]
        with patch.object(sys,'argv',args),patch.object(sys,'platform',host),\
                patch.object(player.subprocess,'run',side_effect=query),redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT/'tools/debug.py'),run_name='__main__')

    def test_no_game_or_unrelated_process_allows_enable_and_disable(self):
        (ROOT/'local-only').mkdir(exist_ok=True)
        cases=(('win32',''),('win32','INFO: No tasks are running.'),
               ('win32','"CW3.exe.Helper","42","Console","1","10 K"\n'),
               ('darwin',''),('darwin','42 /Applications/Steam.app/Contents/MacOS/Steam\n43 /Games/CW3.app/Contents/MacOS/CW3Helper'))
        for host,processes in cases:
            for mode in ('enable','disable'):
                with self.subTest(host=host,mode=mode,processes=processes),tempfile.TemporaryDirectory(dir=ROOT/'local-only') as folder:
                    config,build,game=self.fixture(Path(folder),mode);self.invoke(host,mode,config,build,processes)
                    self.assertEqual((game/'CW3_Data/Managed/Assembly-CSharp.dll').read_bytes(),b'debug core' if mode=='enable' else b'base core')
                    self.assertEqual((game/'CW3_Data/Managed/CW3Debug.dll').exists(),mode=='enable')
                    self.assertEqual((game/'keep.txt').read_bytes(),b'unrelated file')

    def test_running_windows_native_mac_or_crossover_game_refuses_changes(self):
        (ROOT/'local-only').mkdir(exist_ok=True)
        cases=(('win32','"cW3.ExE","42","Console","1","10 K"\n'),
               ('darwin','42 /Games/CW3.app/Contents/MacOS/CW3'),
               ('darwin','42 /Games/CW3.app/Contents/MacOS/Menu Helper'),
               ('darwin','42 wine C:\\游戏 with spaces\\CW3.exe -windowed'))
        for host,processes in cases:
            for mode in ('enable','disable'):
                with self.subTest(host=host,mode=mode),tempfile.TemporaryDirectory(dir=ROOT/'local-only') as folder:
                    config,build,game=self.fixture(Path(folder),mode);before=self.snapshot(game)
                    with self.assertRaisesRegex(RuntimeError,'完全退出'):self.invoke(host,mode,config,build,processes)
                    self.assertEqual(self.snapshot(game),before)

    def test_failed_or_unavailable_query_never_changes_game(self):
        (ROOT/'local-only').mkdir(exist_ok=True)
        for host in ('win32','darwin'):
            for mode in ('enable','disable'):
                for error in ('failure','missing'):
                    with self.subTest(host=host,mode=mode,error=error),tempfile.TemporaryDirectory(dir=ROOT/'local-only') as folder:
                        config,build,game=self.fixture(Path(folder),mode);before=self.snapshot(game)
                        with self.assertRaises((RuntimeError,subprocess.CalledProcessError,FileNotFoundError)):
                            self.invoke(host,mode,config,build,error=error)
                        self.assertEqual(self.snapshot(game),before)


if __name__=='__main__':unittest.main()
