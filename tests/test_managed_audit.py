"""Cecil output retains exact literal evidence and rejects malformed or unsafe report output."""
from pathlib import Path
import base64,subprocess,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_managed_display import rows
ROOT=Path(__file__).resolve().parents[1]
class ManagedAuditRows(unittest.TestCase):
    def test_multiline_unicode_and_unknown_consumer_remain_exact(self):
        b=lambda s:base64.b64encode(s.encode()).decode();text='Quoted\ttext\n中文 = value'
        row=rows('\t'.join(['unknown','unknown','100663300','7','21',b('System.Void Fixture::Call()'),b(text),b(''),b('Literal consumed by Unknown::Call'),b(''),''])+'\n')[0]
        self.assertEqual(row['source'],text);self.assertEqual(row['classification'],'unknown');self.assertIsNone(row['binding_id']);self.assertEqual(row['il_offset'],21)
    def test_report_must_be_new_and_local_before_config_access(self):
        r=subprocess.run([sys.executable,str(ROOT/'tools/audit_managed_display.py'),'--config','/nonexistent/cw3.json','--output','/tmp/not-a-project-report.json'],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);self.assertIn('new local-only',r.stderr);self.assertNotIn('FileNotFoundError',r.stderr)
if __name__=='__main__':unittest.main()
