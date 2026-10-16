"""Cecil output retains exact literal evidence and rejects malformed or unsafe report output."""
from pathlib import Path
import base64,io,json,subprocess,sys,tempfile,unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_managed_display
from audit_managed_display import rows
ROOT=Path(__file__).resolve().parents[1]
class ManagedAuditRows(unittest.TestCase):
    def test_multiline_unicode_and_unknown_consumer_remain_exact(self):
        b=lambda s:base64.b64encode(s.encode()).decode();text='Quoted\ttext\n中文 = value'
        row=rows('\t'.join(['unknown','unknown','100663300','7','21',b('System.Void Fixture::Call()'),b(text),b(''),b('Literal consumed by Unknown::Call'),b('')])+'\n')[0]
        self.assertEqual(row['source'],text);self.assertEqual(row['classification'],'unknown');self.assertIsNone(row['binding_id']);self.assertEqual(row['il_offset'],21)
    def test_report_must_be_new_and_local_before_config_access(self):
        r=subprocess.run([sys.executable,str(ROOT/'tools/audit_managed_display.py'),'--config','/nonexistent/cw3.json','--output','/tmp/not-a-project-report.json'],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);self.assertIn('new local-only',r.stderr);self.assertNotIn('FileNotFoundError',r.stderr)
    def test_dictionary_snapshot_is_utf8_with_legacy_windows_default_encodings(self):
        dictionary=json.loads((ROOT/'translations/zh-CN.json').read_bytes())
        (ROOT/'local-only').mkdir(exist_ok=True)
        write_text=Path.write_text
        for default_encoding in ('cp1252','gbk'):
            with self.subTest(default_encoding=default_encoding),tempfile.TemporaryDirectory(dir=ROOT/'local-only') as folder:
                root=Path(folder);original=root/'original';assembly=original/'CW3_Data/Managed/Assembly-CSharp.dll'
                assembly.parent.mkdir(parents=True);assembly.write_bytes(b'synthetic assembly')
                config=root/'config.json';config.write_text(json.dumps(dict(target_id='windows-steam-22453699',original=str(original))),encoding='utf-8')
                snapshots=[]
                def run(exe,args,capture):
                    # Match the C# consumer's UTF-8 input contract at the process boundary.
                    snapshots.append(json.loads(Path(args[1]).read_bytes().decode('utf-8')))
                    return SimpleNamespace(stdout='')
                mono=SimpleNamespace(location=lambda key:original,prepare_cecil=lambda out:'',
                    compile=lambda out,name,sources,flags:out/name,win=str,run=run)
                def legacy_write(path,data,encoding=None,errors=None,newline=None):
                    return write_text(path,data,encoding=encoding or default_encoding,errors=errors,newline=newline)
                args=['audit_managed_display.py','--config',str(config),'--output',str(root/'report.json')]
                with patch.object(sys,'argv',args),patch.object(Path,'write_text',legacy_write),\
                        patch.object(audit_managed_display,'MonoTools',return_value=mono),\
                        patch.object(audit_managed_display,'audit_dictionary',return_value=dictionary),redirect_stdout(io.StringIO()):
                    audit_managed_display.main()
                self.assertEqual(snapshots,[dictionary])
if __name__=='__main__':unittest.main()
