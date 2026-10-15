import json, sys, unittest, tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import independent

class SlimResources(unittest.TestCase):
    def test_dirty_output_is_rejected_before_loading_inputs(self):
        for leftover in ('manifest.json','files/CW3_Data/Managed/CW3Debug.dll','files/CW3_Data/output_log.txt','empty-directory'):
            with self.subTest(leftover=leftover),tempfile.TemporaryDirectory() as folder:
                out=Path(folder)/'candidate';target=out/leftover;target.parent.mkdir(parents=True)
                if leftover=='empty-directory':target.mkdir()
                else:target.write_bytes(b'KEEP')
                with self.assertRaisesRegex(ValueError,'empty output directory'):independent.build({},out)
                if leftover!='empty-directory':self.assertEqual(target.read_bytes(),b'KEEP')
                self.assertFalse((out/'generated').exists())

    def test_wrong_sans_hash_is_rejected_at_build_entry(self):
        from fontTools.ttLib import TTFont
        import text_style
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'fonts').mkdir();(root/'local-only/independent-font').mkdir(parents=True)
            (root/'fonts/provenance.json').write_text((independent.ROOT/'fonts/provenance.json').read_text())
            # Still a valid, correctly named static font, so family/cmap alone
            # cannot distinguish this unapproved binary from the controlled input.
            with TTFont(independent.ROOT/'fonts/CW3SansSC-Regular.ttf') as font:
                for row in font['name'].names:
                    if row.nameID in (1,16):row.string='CW3 Sans SC External Fixture'.encode(row.getEncoding())
                font.save(root/'local-only/independent-font/font.ttf')
            self.assertTrue(text_style.validate_font(root/'local-only/independent-font/font.ttf','sans'))
            out=root/'candidate'
            with patch.object(independent,'ROOT',root),self.assertRaisesRegex(ValueError,'Font hash differs'):
                independent.build({},out)
            self.assertFalse(out.exists())

    def test_only_four_repaired_resources_are_serialized(self):
        layout=json.loads((independent.ROOT/'resources/layout.json').read_text())
        plan=list(independent.resource_plan(layout))
        self.assertEqual({name for name,fixes,font in plan},{'CW3_Data/level2','CW3_Data/level3','CW3_Data/sharedassets0.assets','CW3_Data/sharedassets2.assets'})
        audio_resource=next(fixes for name,fixes,font in plan if name.endswith('sharedassets2.assets'))
        self.assertEqual({f['object_id'] for f in audio_resource if f['kind']=='raw_fixed'},{288,289,290})
        background=[f for f in audio_resource if f['kind']=='fields']
        self.assertEqual(len(background),166)
        self.assertEqual(len({f['object_id'] for f in background}),166)
        self.assertTrue({81,104,229}.isdisjoint(f['object_id'] for f in background))
        self.assertTrue(all(f['fields']=={'m_LoadInBackground':{'before':False,'after':True}} for f in background))
        self.assertEqual([name for name,fixes,font in plan if font],['CW3_Data/sharedassets0.assets'])
    def test_embedded_font_alone_still_requires_resource_output(self):
        layout=dict(original_hashes={'CW3_Data/sharedassets0.assets':'sha','CW3_Data/resources.assets':'sha'},fixed_edits=[])
        self.assertEqual(list(independent.resource_plan(layout)),[('CW3_Data/sharedassets0.assets',[],True)])

    def test_native_audio_edits_match_the_audited_windows_ids(self):
        windows=json.loads((independent.ROOT/'resources/layout.json').read_text())
        native=json.loads((independent.ROOT/'resources/macos-target.json').read_text())
        def background(profile):
            return [row for row in profile['fixed_edits'] if row.get('fields')=={'m_LoadInBackground':{'before':False,'after':True}}]
        self.assertEqual(len(background(native)),166)
        self.assertEqual(background(native),background(windows))
        self.assertTrue({81,104,229}.isdisjoint(row['object_id'] for row in background(native)))
