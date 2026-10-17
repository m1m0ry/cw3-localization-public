"""Selection happens before configuration/runtime access; only requested compilation runs."""
from pathlib import Path
import importlib.util,json,os,shutil,sys,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('contract_runner',ROOT/'tools/test.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
from mono_tools import MonoTools
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

    @unittest.skipIf(os.name=='nt','POSIX command fixtures; public CI uses Ubuntu')
    def test_standalone_selection_uses_system_commands_without_config_or_cecil(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);tools=root/'tools';tools.mkdir();commands=root/'bin';commands.mkdir();record=root/'calls.jsonl'
            for file in ('test.py','mono_tools.py'):shutil.copy2(ROOT/'tools'/file,tools/file)
            (root/'config.local.json').write_text('THIS CONFIG MUST NOT BE READ')
            script='#!'+sys.executable+'\n'+'''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
with open(os.environ['CW3_TEST_TOOL_CALLS'],'a') as out:out.write(json.dumps([name,*sys.argv[1:]])+'\\n')
if name=='mcs':
    target=next(a[len('-out:'):] for a in sys.argv[1:] if a.startswith('-out:'))
    Path(target).write_text('owned compiler boundary fixture')
'''
            for command in ('mono','mcs'):
                path=commands/command;path.write_text(script);path.chmod(0o755)
            env=dict(os.environ,PATH=str(commands)+os.pathsep+os.environ.get('PATH',''),CW3_TEST_TOOL_CALLS=str(record))
            for options in ([],['--standalone']):
                with self.subTest(options=options):
                    record.unlink(missing_ok=True)
                    result=subprocess.run([sys.executable,str(tools/'test.py'),*options,'--suite','FontSettingsContracts','--suite','FontSettingsContracts'],cwd=root,env=env,capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    calls=[json.loads(line) for line in record.read_text().splitlines()]
                    self.assertEqual([call[0] for call in calls],['mcs','mono'])
                    self.assertTrue(calls[1][1].endswith('FontSettingsContracts.exe'))
                    self.assertIn('1 suites; 1 compilations',result.stdout)
            rejected=subprocess.run([sys.executable,str(tools/'test.py'),'--standalone','--suite','GuiCaptionContracts'],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(rejected.returncode,2);self.assertIn('--standalone cannot run',rejected.stderr)
            self.assertNotIn('JSONDecodeError',rejected.stderr)

    def test_configured_mono_resolves_cecil_only_for_consumers(self):
        mono=MonoTools(dict(mono_runtime='/fixture/mono',mono_compiler='/fixture/mcs.exe'))
        with tempfile.TemporaryDirectory() as name, self.assertRaisesRegex(ValueError,'Cecil'):
            mono.prepare_cecil(Path(name))
        crossover=MonoTools(dict(crossover='/fixture/crossover',mono_version='owned-mono'))
        self.assertEqual(crossover.cecil,Path('/fixture/crossover/share/wine/mono/owned-mono/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll'))
if __name__=='__main__':unittest.main()
