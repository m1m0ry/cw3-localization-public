import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import candidates

class CandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = candidates.read(candidates.ROOT/'translations/zh-CN.json')
        self.entry = next(e for e in self.dictionary['entries'] if e['target']['kind']=='label')
        self.row = dict(source=self.entry['source'],kind='label',scene='MainMenu',context='Button/Label',reason='missing_translation',id=self.entry['id'],count=2)
        self.row['key'] = candidates.key(self.row)
    def test_snapshots_of_same_session_do_not_double_count(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[]
            for n,count in enumerate((2,5)):
                path=Path(folder)/str(n);row=dict(self.row,count=count)
                path.write_text(json.dumps(dict(format=1,session='a'*32,candidates=[row])));paths.append(path)
            result=candidates.export(paths,self.dictionary)
            self.assertEqual(result['candidates'][0]['count'],5)
            self.assertEqual(result['candidates'][0]['review'],'translation')
            self.assertFalse(result['candidates'][0]['approved'])
    def test_approved_merge_changes_only_translation(self):
        row=dict(self.row,approved=True,translation='测试')
        result,count=candidates.merge(dict(format=1,kind='cw3-candidate-review',candidates=[row]),self.dictionary)
        expected=copy.deepcopy(self.dictionary)
        next(e for e in expected['entries'] if e['id']==self.entry['id'])['translation']='测试'
        self.assertEqual((result,count),(expected,1))
    def test_unknown_binding_cannot_be_merged(self):
        row=dict(self.row,approved=True,translation='测试',id='unknown',reason='unbound_source');row['key']=candidates.key(row)
        with self.assertRaises(ValueError):
            candidates.merge(dict(format=1,kind='cw3-candidate-review',candidates=[row]),self.dictionary)
    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.json';path.write_text('keep')
            with self.assertRaises(FileExistsError):candidates.write_new(path,{})
            self.assertEqual(path.read_text(),'keep')
    def test_new_binding_reasons_export_through_cli_and_stay_unmergeable(self):
        import subprocess
        reasons=('unknown_resource','unbound_target','ambiguous_target','message_list_mismatch','unknown_message_list')
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            rows=[dict(self.row,id='',reason=reason) for reason in reasons]+[self.row]
            for row in rows: row['key']=candidates.key(row)
            snapshot=folder/'snapshot.json';snapshot.write_text(json.dumps(dict(format=1,session='a'*32,candidates=rows)))
            output=folder/'review.json'
            result=subprocess.run([sys.executable,str(candidates.ROOT/'tools/candidates.py'),'export',str(snapshot),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            review=candidates.read(output)
            self.assertEqual({r['reason'] for r in review['candidates']},set(reasons)|{'missing_translation'})
            for row in review['candidates']:
                if row['reason']=='missing_translation': continue
                self.assertEqual(row['review'],'binding');self.assertIsNone(row['target_hint'])
                row.update(approved=True,translation='测试')
                with self.assertRaises(ValueError): candidates.merge(review,self.dictionary)
                row['approved']=False
    def test_truly_invalid_reason_rejects_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'snapshot.json';row=dict(self.row,reason='invented_status');row['key']=candidates.key(row)
            path.write_text(json.dumps(dict(format=1,session='a'*32,candidates=[row])))
            with self.assertRaisesRegex(ValueError,'Invalid candidate'): candidates.export([path],self.dictionary)
