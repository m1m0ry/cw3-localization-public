"""Use committed font data to guard dictionary glyph coverage."""
from pathlib import Path
import base64, sys, tempfile, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import font_registry

class NativeCoverage(unittest.TestCase):
    def test_serif_coverage_distinguishes_own_glyphs_from_os_fallback(self):
        font=Path(__file__).resolve().parents[1]/'fonts/CW3SerifSC-Regular.ttf'
        bits=base64.b64decode(font_registry.inspect_font(font)['coverage'])
        self.assertEqual(len(bits),8192)
        for char in 'W泰赫摸章绩芒':
            self.assertTrue(bits[ord(char)//8] & (1<<(ord(char)%8)),char)
        self.assertFalse(bits[ord('龘')//8] & (1<<(ord('龘')%8)))
        self.assertFalse(bits[0] & 1)  # .notdef is never accepted as character coverage.

    def test_build_font_metadata_rejects_unsafe_paths_and_damaged_sources(self):
        # The resource importer is retired; controlled build metadata still validates sources.
        for value in ('../font.ttf','fonts/../../font.ttf','fonts/X.ttf','fonts/a.woff'):
            with self.assertRaises(ValueError):font_registry.font_path(value)
        for value in ('../a','A','a/b','a\n'):
            with self.assertRaises(ValueError):font_registry.font_id(value)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.woff';path.write_bytes(b'not a font')
            with self.assertRaises(ValueError):font_registry.inspect_font(path)
            path=Path(folder)/'broken.ttf';path.write_bytes(b'not a font')
            with self.assertRaisesRegex(ValueError,'damaged'):font_registry.inspect_font(path)
