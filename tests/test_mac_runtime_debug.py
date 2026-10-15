"""The resident Mac diagnostics controller touches only its explicit State fixture."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mac_runtime_debug as debug
import player_install as player


class RuntimeDebug(unittest.TestCase):
    def fixture(self,root):
        game=root/'game';state=root/'persistent'/'CW3Localization'
        state.mkdir(parents=True);(state/'font-status.json').write_text('{}')
        manifest=dict(target_id=player.MACOS,**player.TARGETS[player.MACOS])
        runtime=game/debug.RUNTIME;runtime.parent.mkdir(parents=True);runtime.write_bytes(b'fixed runtime')
        digest=hashlib.sha256(b'fixed runtime').hexdigest()
        manifest['files']=[dict(file=debug.RUNTIME,before=None,after=digest)]
        backup=game/player.BACKUP;backup.mkdir();(backup/'state.json').write_text(json.dumps(manifest))
        return game,state,runtime

    def test_marker_is_locked_to_installed_external_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            game,state,runtime=self.fixture(Path(directory))
            with patch.object(player,'idle'):
                debug.action(game,state,['enable'],Path(directory)/'evidence')
                marker=state/'cw3-debug/enabled.txt'
                self.assertEqual(marker.read_text().strip(),player.digest(runtime))
                runtime.write_bytes(b'other runtime')
                with self.assertRaisesRegex(RuntimeError,'differs'):debug.action(game,state,['disable'],Path(directory)/'evidence')
                runtime.write_bytes(b'fixed runtime')
                debug.action(game,state,['disable'],Path(directory)/'evidence')
            self.assertFalse(marker.exists())

    def test_rejects_unlisted_command_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            game,state,_=self.fixture(Path(directory))
            with patch.object(player,'idle'):debug.action(game,state,['enable'],Path(directory)/'evidence')
            for command in ('arbitrary','tutorial_preview','tutorial_run'):
                with self.subTest(command=command),self.assertRaises(ValueError):
                    debug.action(game,state,['command',command],Path(directory)/'evidence')
            self.assertFalse((state/'cw3-debug/request.txt').exists())

    def test_preview_and_probe_commands_reject_path_or_code_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            game,state,_=self.fixture(Path(directory))
            with patch.object(player,'idle'):debug.action(game,state,['enable'],Path(directory)/'evidence')
            for command in ('prelude_preview','preview_return',
                            'quit','display_probe','fonts_probe','fallback_probe','audio_probe'):
                with self.subTest(command=command),self.assertRaisesRegex(ValueError,'Unexpected'):
                    debug.action(game,state,['command',command,'/outside/fixture'],Path(directory)/'evidence')
                self.assertFalse((state/'cw3-debug/request.txt').exists())


if __name__=='__main__':unittest.main()
