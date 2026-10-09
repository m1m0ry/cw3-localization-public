import json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import independent

class SlimResources(unittest.TestCase):
    def test_only_four_repaired_resources_are_serialized(self):
        layout=json.loads((independent.ROOT/'resources/layout.json').read_text())
        plan=list(independent.resource_plan(layout))
        self.assertEqual({name for name,fixes,font in plan},{'CW3_Data/level2','CW3_Data/level3','CW3_Data/sharedassets0.assets','CW3_Data/sharedassets2.assets'})
        self.assertEqual({f['object_id'] for name,fixes,font in plan if name.endswith('sharedassets2.assets') for f in fixes},{288,289,290})
        self.assertEqual([name for name,fixes,font in plan if font],['CW3_Data/sharedassets0.assets'])
    def test_embedded_font_alone_still_requires_resource_output(self):
        layout=dict(original_hashes={'CW3_Data/sharedassets0.assets':'sha','CW3_Data/resources.assets':'sha'},fixed_edits=[])
        self.assertEqual(list(independent.resource_plan(layout)),[('CW3_Data/sharedassets0.assets',[],True)])
