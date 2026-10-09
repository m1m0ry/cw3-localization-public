"""Selection happens before configuration/runtime access; only requested compilation runs."""
from pathlib import Path
import importlib.util,sys,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('contract_runner',ROOT/'tools/test.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class TestSelection(unittest.TestCase):
    def test_list_and_invalid_selection_do_not_load_config(self):
        base=[sys.executable,str(ROOT/'tools/test.py'),'--config','/nonexistent/cw3-config.json']
        listed=subprocess.run(base+['--list'],capture_output=True,text=True);self.assertEqual(listed.returncode,0);self.assertEqual(listed.stdout.splitlines(),list(runner.SUITES))
        bad=subprocess.run(base+['--suite','Unknown'],capture_output=True,text=True);self.assertEqual(bad.returncode,2);self.assertIn('invalid choice',bad.stderr);self.assertNotIn('FileNotFoundError',bad.stderr)
    def test_gui_selection_needs_no_font_game_or_definitions(self):
        class Compiler:
            def __init__(self):self.compiled=[];self.executed=[]
            def win(self,p):return str(p)
            def prepare_cecil(self,o):return '-r:Cecil'
            def compile(self,o,name,sources,flags):self.compiled.append((name,[p.name for p in sources]));return o/name
            def run(self,exe,args):self.executed.append(exe.name)
            def location(self,key):raise AssertionError('Unexpected prerequisite: '+key)
        with tempfile.TemporaryDirectory()as d:
            m=Compiler();runner.Contracts(m,Path(d)).suite('GuiCaptionContracts')
            self.assertEqual(m.compiled,[('GuiCaptionContracts.exe',['GuiCaptionAudit.cs','GuiCaptionContracts.cs'])]);self.assertEqual(m.executed,['GuiCaptionContracts.exe'])
if __name__=='__main__':unittest.main()
