import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from package_audio_addon import ASSET, baseline


class AudioAddonBaseline(unittest.TestCase):
    def test_only_matching_localized_package_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / ASSET
            asset.parent.mkdir()
            raw = b'localized resource including existing font repairs'
            asset.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            spec = dict(baseline_sha256=digest)
            supported = dict(exe_sha256='supported-executable')
            manifest = dict(format=2, version='candidate', exe_sha256='supported-executable',
                            files=[dict(file=ASSET, after=digest, bytes=len(raw))])
            self.assertEqual(baseline(root, manifest, spec, supported), raw)
            cases = []
            wrong_game = copy.deepcopy(manifest)
            wrong_game['exe_sha256'] = 'other-version'
            cases.append(wrong_game)
            original = copy.deepcopy(manifest)
            original['files'][0]['after'] = 'original-not-localized'
            cases.append(original)
            missing = copy.deepcopy(manifest)
            missing['files'] = []
            cases.append(missing)
            duplicate = copy.deepcopy(manifest)
            duplicate['files'] *= 2
            cases.append(duplicate)
            for rejected in cases:
                with self.subTest(manifest=rejected), self.assertRaises(ValueError):
                    baseline(root, rejected, spec, supported)
            # A plausible manifest never legitimizes altered on-disk resource bytes.
            asset.write_bytes(b'foreign overlay')
            with self.assertRaises(ValueError):
                baseline(root, manifest, spec, supported)


if __name__ == '__main__':
    unittest.main()
