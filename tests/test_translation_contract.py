"""Contributor guard regressions; no game, UnityPy, compiler or network needed."""
from contextlib import redirect_stdout
from pathlib import Path
import copy
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workflow', ROOT / 'tools/workflow.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

class TranslationContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('translations/zh-CN.json', 'translations/targets.lock.json', 'fonts/codepoints.json'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        workflow.ROOT = self.root
        self.doc = json.loads((self.root / 'translations/zh-CN.json').read_text())

    def check(self, doc):
        (self.root / 'translations/zh-CN.json').write_text(json.dumps(doc, ensure_ascii=False))
        with redirect_stdout(io.StringIO()):
            return workflow.check()

    def test_translation_edit_is_accepted(self):
        self.doc['entries'][0]['translation'] += '！'
        self.assertEqual(self.check(self.doc)[0]['translation'], self.doc['entries'][0]['translation'])

    def test_source_and_internal_target_cannot_drift(self):
        for field, value in (('source', 'changed'), ('target', {'kind': 'label', 'object_id': -1})):
            with self.subTest(field=field):
                doc = copy.deepcopy(self.doc)
                doc['entries'][0][field] = value
                with self.assertRaisesRegex(AssertionError, 'Immutable target/source'):
                    self.check(doc)

    def test_unsafe_display_text_is_rejected(self):
        cases = [('{0}', 'Placeholder/tag mismatch'), ('🧪', 'Font subset needs maintainer update')]
        for suffix, message in cases:
            with self.subTest(suffix=suffix):
                doc = copy.deepcopy(self.doc)
                doc['entries'][0]['translation'] += suffix
                with self.assertRaisesRegex(AssertionError, message):
                    self.check(doc)
        doc = copy.deepcopy(self.doc)
        entry = next(e for e in doc['entries'] if e['target']['kind'] == 'crpl')
        entry['translation'] += '"'
        with self.assertRaisesRegex(AssertionError, 'Unsafe CRPL literal'):
            self.check(doc)

if __name__ == '__main__':
    unittest.main()
