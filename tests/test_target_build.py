"""Target selection and publication boundaries do not require private game files."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import game_target
import independent
import workflow


class TargetBuild(unittest.TestCase):
    def test_target_is_explicit_and_does_not_follow_host(self):
        windows = game_target.load({'target_id':game_target.WINDOWS})
        mac = game_target.load({'target_id': game_target.MACOS})
        self.assertEqual((windows['id'], windows['platform']), (game_target.WINDOWS, 5))
        self.assertEqual((mac['id'], mac['platform']), (game_target.MACOS, 2))
        self.assertEqual(game_target.installed(Path('/game'), 'CW3_Data/Managed/Assembly-CSharp.dll', mac),
                         Path('/game/CW3.app/Contents/Resources/Data/Managed/Assembly-CSharp.dll'))
        for config in ({},{'target_id':'guess'}):
            with self.assertRaises(ValueError):game_target.load(config)
        for name in ('/CW3_Data/x', 'CW3_Data/../x', 'CW3Localization/x'):
            with self.assertRaises(ValueError):game_target.installed(Path('/game'), name, mac)

    def test_installer_and_builder_lock_the_same_executable_versions(self):
        import player_install
        for target_id in (game_target.WINDOWS,game_target.MACOS):
            self.assertEqual(player_install.FINGERPRINTS[target_id],game_target.load({'target_id':target_id})['exe_sha256'])

    def test_snapshot_drift_stops_build_input_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);file = root / 'CW3_Data/mainData';file.parent.mkdir();file.write_bytes(b'original')
            target = {'original_hashes': {'CW3_Data/mainData': hashlib.sha256(b'original').hexdigest()}}
            game_target.verify_inputs(root, target)
            file.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):game_target.verify_inputs(root, target)

    def test_windows_prepare_includes_all_fixed_compiler_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';original=root/'original'
            target=game_target.load({'target_id':game_target.WINDOWS})
            references={'CW3_Data/Managed/'+name for name in ('mscorlib.dll','UnityEngine.dll','System.dll','System.Xml.dll','System.Core.dll')}
            contents={name:name.encode() for name in set(target['original_hashes'])|references}
            for name,data in dict(contents,**{target['executable']:b'EXE'}).items():
                path=game/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            target=dict(target,exe_sha256=hashlib.sha256(b'EXE').hexdigest(),original_hashes={name:hashlib.sha256(contents[name]).hexdigest() for name in target['original_hashes']})
            config=root/'config.json';config.write_text(json.dumps(dict(game=str(game),original=str(original))))
            with patch.object(workflow,'check'),patch.object(game_target,'load',return_value=target),patch.object(sys,'argv',['workflow','prepare','--config',str(config)]):
                workflow.main()
            for name in references:self.assertEqual((original/name).read_bytes(),contents[name])
            game_target.verify_inputs(original,target)
            # A patched installation cannot invalidate already verified cached inputs.
            (game/'CW3_Data/level2').write_bytes(b'PATCHED GAME RESOURCE')
            for missing in (None,'CW3_Data/Managed/UnityEngine.dll'):
                if missing:(original/missing).unlink()
                with patch.object(workflow,'check'),patch.object(game_target,'load',return_value=target),patch.object(sys,'argv',['workflow','prepare','--config',str(config)]):workflow.main()
                game_target.verify_inputs(original,target)
            changed=original/'CW3_Data/Managed/UnityEngine.dll';changed.write_bytes(b'DRIFT')
            with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):game_target.verify_inputs(original,target)

    def test_failed_candidate_is_not_published_or_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);output = root / 'candidate'
            def fail(config, stage, final):
                stage.mkdir();(stage / 'partial').write_text('diagnostic')
                raise ValueError('anchor mismatch')
            with patch.object(independent, '_build', side_effect=fail):
                with self.assertRaisesRegex(ValueError, 'anchor mismatch'):independent.build({'target_id':game_target.WINDOWS}, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_verified_candidate_survives_staging_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);output = root / 'candidate'
            def complete(config, stage, final):
                stage.mkdir();(stage / 'manifest.json').write_text('verified')
            with patch.object(independent, '_build', side_effect=complete):
                independent.build({'target_id':game_target.WINDOWS}, output)
            self.assertEqual((output / 'manifest.json').read_text(), 'verified')
            self.assertEqual(list(root.iterdir()), [output])

    def test_optimized_python_cannot_disable_target_verification(self):
        result = subprocess.run([sys.executable, '-O', '-c',
            'import sys;sys.path.insert(0,"tools");import game_target;game_target.load(dict(target_id=game_target.WINDOWS))'], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('do not use -O', result.stderr)

    def test_native_repairs_include_only_declared_font_dialogue_and_audio_fields(self):
        target = game_target.load({'target_id': game_target.MACOS})
        fixes = target['fixed_edits']
        self.assertEqual(len(fixes), 171)
        self.assertEqual({f['object_id'] for f in fixes if f['kind']=='raw_fixed'}, {288, 289, 290})
        dialogue=[f for f in fixes if f['file'] in ('CW3_Data/level2','CW3_Data/level3')]
        audio=[f for f in fixes if f.get('fields')=={'m_LoadInBackground':{'before':False,'after':True}}]
        self.assertEqual(len(dialogue),2)
        self.assertEqual(len(audio),166)
        self.assertEqual({f['file'] for f in audio},{'CW3_Data/sharedassets2.assets'})


if __name__ == '__main__':unittest.main()
