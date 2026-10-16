"""Retired build-time user fonts cannot re-enter controlled resource packages."""
from pathlib import Path
import base64
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import font_registry
import package_player
SUPPORTED=json.loads((ROOT/'resources/supported-build.json').read_text())


class LegacyFontRetirement(unittest.TestCase):
    def test_registry_paths_are_only_the_shipped_faces(self):
        for name in ('font.ttf', 'serif.ttf'):
            self.assertEqual(font_registry.font_path(name), name)
        for name in ('zpix.ttf', 'pixel.ttf', 'fonts/pixel.ttf', 'fonts/zpix.ttf', 'fonts/../zpix.ttf'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                font_registry.font_path(name)

    def test_default_face_cannot_use_the_other_faces_file(self):
        from player_fixture import registry
        doc=registry()
        font_registry.validate(doc)
        doc['fonts']['serif']['file']='font.ttf'
        with self.assertRaisesRegex(ValueError,'face/path mismatch'):
            font_registry.validate(doc)

    def test_builder_rejects_retired_option_before_reading_inputs(self):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/independent.py'),
                                 '--local-menu-font', 'zpix.ttf'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('unrecognized arguments: --local-menu-font', result.stderr)

    def package_fixture(self, root, legacy=False):
        package=root/'candidate';build=root/'files';package.mkdir();build.mkdir()
        (package/'manifest.json').write_text(json.dumps(dict(SUPPORTED,
            revision='independent-v12-candidate', local_menu_font={'sha256':'0'*64} if legacy else None)))
        config=root/'config.json';config.write_text(json.dumps(dict(package=str(package),build=str(build))))
        return config,build,root/'local-only/package'

    def test_old_manifest_safety_gate_still_blocks_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config,_,out=self.package_fixture(root,legacy=True)
            argv=['package_player.py','--config',str(config),'--output',str(out)]
            supported=SUPPORTED;(root/'resources').mkdir()
            (root/'resources/supported-build.json').write_text(json.dumps(supported))
            with patch.object(package_player,'ROOT',root),patch.object(sys,'argv',argv):
                with self.assertRaisesRegex(AssertionError,'distribution is not authorized'):
                    package_player.main()
            self.assertFalse(out.exists())

    def test_generic_user_registry_safety_gate_still_blocks_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config,build,out=self.package_fixture(root)
            (root/'resources').mkdir();(root/'resources/supported-build.json').write_text(json.dumps(SUPPORTED))
            folder=build/'CW3Localization';folder.mkdir()
            face=lambda file:dict(file=file,sha256='0'*64,family='Fixture',coverage=base64.b64encode(bytes(8192)).decode(),pixel_size=0,probe_char=65,probe_advance=20)
            registry=dict(format=1,runtime_sha256='0'*64,resources={key:'0'*64 for key in font_registry.RESOURCES},fonts={'sans':face('font.ttf'),'serif':face('serif.ttf'),'pixel':face('fonts/pixel.ttf')})
            (folder/'fonts.json').write_text(json.dumps(registry))
            argv=['package_player.py','--config',str(config),'--output',str(out)]
            with patch.object(package_player,'ROOT',root),patch.object(sys,'argv',argv):
                with self.assertRaisesRegex(ValueError,'only shipped sans/serif'):
                    package_player.main()
            self.assertFalse(out.exists())


    def test_settings_template_cannot_reenter_an_overwrite_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config,_,out=self.package_fixture(root)
            (root/'resources').mkdir();(root/'resources/supported-build.json').write_text(json.dumps(SUPPORTED))
            candidate=root/'candidate/manifest.json';doc=json.loads(candidate.read_text())
            doc['files']=[dict(file='CW3Localization/text-style.json')];candidate.write_text(json.dumps(doc))
            argv=['package_player.py','--config',str(config),'--output',str(out)]
            with patch.object(package_player,'ROOT',root),patch.object(sys,'argv',argv),self.assertRaisesRegex(AssertionError,'settings template'):
                package_player.main()
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
