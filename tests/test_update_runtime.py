"""Transaction failures must restore installed files, build files and manifest."""
import json, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import update_runtime as updater
import translation_contract as contract
ROOT = Path(__file__).resolve().parents[1]

class RuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game, self.build, self.package = [self.root / n for n in ('game','build','package')]
        self.package.mkdir()
        self.names = ['CW3Localization/zh-CN.json','CW3Localization/font.ttf']
        rows = []
        for name in self.names:
            data = ('old-' + name).encode()
            for base in (self.game, self.build):
                p = base / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
            rows.append(dict(file=name, after=updater.sha(data), bytes=len(data)))
        self.manifest = self.package / 'manifest.json'
        self.manifest.write_text(json.dumps(dict(revision='independent-v12-candidate', files=rows)))
        self.dictionary, self.font = self.root/'new.json', self.root/'new.ttf'
        self.dictionary.write_bytes(b'new dictionary'); self.font.write_bytes(b'new font')
        self.config = dict(game=str(self.game),build=str(self.build),package=str(self.package))
        self.original = {p:p.read_bytes() for p in [self.manifest] + [base/name for base in (self.game,self.build) for name in self.names]}

    def restored(self):
        for path, data in self.original.items(): self.assertEqual(path.read_bytes(), data, str(path))
        self.assertFalse(list(self.root.rglob('*runtime-update-tmp')))

    def failure(self, operation, fail_at, corrupt=False):
        real = getattr(updater.os if operation=='replace' else updater.shutil, operation)
        fired = []
        def injected(source, target, *args, **kwargs):
            target = Path(target)
            if not fired and fail_at(source, target):
                fired.append(True)
                if corrupt:
                    target.write_bytes(b'partial corrupt copy'); return str(target)
                if operation=='copyfile': target.write_bytes(b'partial')
                raise OSError('injected ' + operation)
            return real(source, target, *args, **kwargs)
        owner = updater.os if operation=='replace' else updater.shutil
        with patch.object(updater, 'validate', return_value=1377), patch.object(updater.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')), patch.object(owner, operation, side_effect=injected):
            with self.assertRaises((OSError, AssertionError)):
                updater.update(self.config,self.dictionary,self.font)
        self.assertTrue(fired); self.restored()
        self.assertTrue((self.package/'runtime-update-backup/manifest.json').exists())

    def test_partial_copy_failure_restores_all(self):
        self.failure('copyfile', lambda source,target: Path(source)==self.dictionary and target.parent==self.game/'CW3Localization')
    def test_hash_failure_cleans_temp_and_restores_all(self):
        self.failure('copyfile', lambda source,target: Path(source)==self.dictionary and target.parent==self.game/'CW3Localization',corrupt=True)
    def test_replace_failure_restores_all(self):
        self.failure('replace', lambda source,target: target==self.game/self.names[0])
    def test_second_file_failure_restores_already_updated_dictionary(self):
        self.failure('replace', lambda source,target: target==self.game/self.names[1])
    def test_manifest_replace_failure_restores_all(self):
        self.failure('replace', lambda source,target: target==self.manifest)
    def test_second_build_copy_failure_restores_both_updated_game_files(self):
        self.failure('replace', lambda source,target: target==self.build/self.names[1])
    def test_success_updates_both_copies_and_manifest(self):
        with patch.object(updater, 'validate', return_value=1377), patch.object(updater.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')):
            updater.update(self.config,self.dictionary,self.font)
        for base in (self.game,self.build):
            self.assertEqual((base/self.names[0]).read_bytes(),self.dictionary.read_bytes())
            self.assertEqual((base/self.names[1]).read_bytes(),self.font.read_bytes())
        for row in json.loads(self.manifest.read_text())['files']:
            self.assertEqual(row['after'],updater.sha((self.game/row['file']).read_bytes()))
        self.assertFalse((self.package/'runtime-update-backup').exists())
        self.assertFalse(list(self.root.rglob('*runtime-update-tmp')))

class DictionaryParityTests(unittest.TestCase):
    def test_shared_invalid_json_cases(self):
        for text in json.loads((ROOT/'tests/json_rejected.json').read_text()):
            with self.subTest(text=text), self.assertRaises(ValueError): contract.loads(text)
    def test_complete_target_set_and_boolean_format(self):
        doc=contract.read(ROOT/'translations/zh-CN.json'); locks=contract.read(ROOT/'translations/targets.lock.json')
        cps=json.loads((ROOT/'fonts/codepoints.json').read_text())
        for changed in (dict(doc,entries=doc['entries'][:-1]),dict(doc,entries=doc['entries']+[doc['entries'][0]]),dict(doc,format=True)):
            with self.assertRaises(AssertionError): contract.check(changed,locks,cps)
    def test_update_uses_same_complete_checker(self):
        doc=contract.read(ROOT/'translations/zh-CN.json'); doc['entries'].pop()
        fake=ModuleType('fontTools.ttLib')
        class Font:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def __contains__(self,key): return False
            def __getitem__(self,key): return SimpleNamespace(names=[SimpleNamespace(nameID=1,toUnicode=lambda:'CW3 Sans SC External test')])
            def getBestCmap(self): return {}
        fake.TTFont=lambda _:Font()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dict.json';p.write_text(json.dumps(doc))
            with patch.dict(sys.modules,{'fontTools.ttLib':fake}), self.assertRaisesRegex(AssertionError,'fixed target set'):
                updater.validate(p,Path(d)/'font.ttf')
