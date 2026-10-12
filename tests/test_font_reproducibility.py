"""Font generation must preserve controlled bytes across clock changes."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]


class FontReproducibility(unittest.TestCase):
    def test_fixed_input_and_recipe_ignore_build_clock(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); (root/'fonts').mkdir(); (root/'tools').mkdir()
            builder = FontBuilder(1000, isTTF=True)
            builder.setupGlyphOrder(['.notdef', 'A'])
            builder.setupCharacterMap({65:'A'})
            glyphs = {}
            for glyph in ['.notdef', 'A']:
                pen = TTGlyphPen(None)
                pen.moveTo((0,0));pen.lineTo((100,0));pen.lineTo((100,100));pen.closePath()
                glyphs[glyph] = pen.glyph()
            builder.setupGlyf(glyphs)
            builder.setupHorizontalMetrics({g:(500,0) for g in glyphs})
            builder.setupHorizontalHeader(ascent=800, descent=-200)
            builder.setupNameTable(dict(familyName='Fixture',styleName='Regular',uniqueFontIdentifier='Fixture',fullName='Fixture',psName='Fixture'))
            builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
            builder.setupPost();builder.setupMaxp()
            builder.setupFvar([('wght',100,400,900,'Weight')], [])
            source = root/'source.ttf';builder.save(source)
            provenance = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                              subset_head_modified=3800000000,external_full_head_modified=3800000001)
            for metadata in ['provenance.json','serif-provenance.json']:
                (root/'fonts'/metadata).write_text(json.dumps(provenance))
            (root/'fonts/codepoints.json').write_text('[65]')
            for script, flags, timestamp in [('build_font.py',[],3800000000),
                                             ('build_font.py',['--external-full'],3800000001),
                                             ('build_serif_font.py',[],3800000000)]:
                with self.subTest(script=script,flags=flags):
                    shutil.copy2(ROOT/'tools'/script,root/'tools'/script)
                    results = []
                    for epoch in ['1700000000','1800000000']:
                        output = root/(script+str(len(flags))+epoch+'.ttf')
                        subprocess.run([sys.executable,str(root/'tools'/script),str(source),str(output),*flags],
                                       check=True,capture_output=True,env=dict(os.environ,SOURCE_DATE_EPOCH=epoch))
                        results.append(output.read_bytes())
                        with TTFont(output,recalcTimestamp=False) as font:
                            self.assertEqual(font['head'].modified,timestamp)
                            self.assertNotIn('fvar',font)
                            self.assertIn(65,font.getBestCmap())
                    self.assertEqual(results[0],results[1])


if __name__ == '__main__':
    unittest.main()
