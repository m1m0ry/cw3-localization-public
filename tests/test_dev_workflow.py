"""Maintenance orchestration tests use isolated files and fake desktop operations only."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import dev
import dev_environment as env
import dev_session as session


class FakeDesktop:
    def __init__(self, root):
        self.game=root/'game';self.state=root/'state';self.events=[];self.running=[];self.timeout_once=False
        self.capture=root/'screen.png'
    def processes(self):return self.running
    def quit(self,timeout):self.events.append('quit');self.running=[]
    def install(self,package,manifest):
        self.events.append('install')
        target=self.game/'CW3.app/Contents/Resources/Data/Managed/CW3Rendering.dll'
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((package/'CW3Rendering.dll').read_bytes())
    def enable(self):self.events.append('enable')
    def launch(self):self.events.append('launch');self.running=[77]
    def exchange(self,record,command,persist,timeout):
        self.events.append(command)
        if self.timeout_once:self.timeout_once=False;raise TimeoutError('waiting')
        result={'scene':'MainMenu','controls':[{'text':'开始'}]}
        if command=='screenshot':self.capture.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB`\x82');result={'path':str(self.capture),'queued':True}
        record['evidence'][command]={'ok':True,'result':result};persist();return result


class WorkflowTests(unittest.TestCase):
    def fixture(self,root):
        package=root/'package';package.mkdir();dll=package/'CW3Rendering.dll';dll.write_bytes(b'candidate')
        session.save(package/'manifest.json',dict(format=1,kind='rendering_component',target_id=session.game_target.MACOS,sha256=hashlib.sha256(b'candidate').hexdigest()))
        backend=FakeDesktop(root)
        record=session.new_session(dict(game=str(backend.game),state=str(backend.state)),package)
        path=root/'session.json'
        return record,backend,lambda:session.save(path,record)

    def test_smoke_pipeline_order_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));session.advance(record,persist,b,.01)
            self.assertEqual(b.events,['quit','install','enable','launch','runtime_probe','display_probe','screenshot'])
            self.assertEqual(record['phase'],'verified');self.assertEqual(record['pids'],[77])
            session.advance(record,persist,b,.01)
            self.assertEqual(b.events.count('install'),1);self.assertEqual(b.events.count('launch'),1)

    def test_timeout_preserves_install_and_resume_does_not_relaunch(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));b.timeout_once=True
            with self.assertRaises(TimeoutError):session.advance(record,persist,b,.01)
            self.assertEqual(record['phase'],'waiting_runtime')
            self.assertEqual(session.installed_hashes(b.game,session.package_identity(Path(record['package']))[0]),record['installed'])
            session.advance(record,persist,b,.01)
            self.assertEqual(b.events.count('quit'),1);self.assertEqual(b.events.count('install'),1);self.assertEqual(b.events.count('launch'),1)

    def test_interrupted_launch_never_blindly_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));b.timeout_once=True
            with self.assertRaises(TimeoutError):session.advance(record,persist,b,.01)
            record['phase']='starting';b.running=[]
            with self.assertRaisesRegex(RuntimeError,'unknown'):session.advance(record,persist,b,.01)
            self.assertEqual(b.events.count('launch'),1)
            b.running=[78];record.pop('pids',None)
            session.advance(record,persist,b,.01)
            self.assertEqual(b.events.count('launch'),1)

    def test_installed_version_or_process_change_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));b.timeout_once=True
            with self.assertRaises(TimeoutError):session.advance(record,persist,b,.01)
            b.running=[88]
            with self.assertRaisesRegex(RuntimeError,'process changed'):session.advance(record,persist,b,.01)
            b.running=[77]
            (b.game/'CW3.app/Contents/Resources/Data/Managed/CW3Rendering.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'candidate changed'):session.advance(record,persist,b,.01)

    def test_candidate_changed_does_not_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp))
            (Path(record['package'])/'CW3Rendering.dll').write_bytes(b'other')
            with self.assertRaises(ValueError):session.advance(record,persist,b,.01)
            self.assertEqual(b.events,[])

    def test_quit_failure_does_not_mutate_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp))
            with patch.object(b,'quit',side_effect=TimeoutError('quit')):
                with self.assertRaises(TimeoutError):session.advance(record,persist,b,.01)
            self.assertEqual(record['phase'],'prepared');self.assertNotIn('install',b.events)

    def test_failed_install_resumes_same_candidate_not_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp))
            with patch.object(b,'install',side_effect=OSError('offline')):
                with self.assertRaises(OSError):session.advance(record,persist,b,.01)
            self.assertEqual(record['phase'],'installing')
            session.advance(record,persist,b,.01)
            self.assertEqual(b.events.count('quit'),1)

    def test_screenshot_file_must_exist_not_just_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));session.advance(record,persist,b,.01)
            b.capture.unlink();record['phase']='checking'
            with self.assertRaises(TimeoutError):session.advance(record,persist,b,.001)
            self.assertEqual(b.events.count('screenshot'),1)
            b.capture.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB`\x82')
            session.advance(record,persist,b,.01)
            self.assertEqual(record['phase'],'verified')

    def test_scope_selects_only_supported_incremental_route(self):
        self.assertEqual(dev.classify([]),'none')
        self.assertEqual(dev.classify(['tools/independent.py','tests/test_any.py']),'source')
        self.assertEqual(dev.classify(['src/rendering/CW3Rendering.cs','tests/RenderingCacheContracts.cs']),'rendering')
        self.assertEqual(dev.classify(['src/runtime/RuntimePaths.cs']),'package')
        self.assertEqual(dev.classify(['src/rendering/CW3Rendering.cs','resources/layout.json']),'package')

    def test_process_query_matches_full_executable_and_rejects_errors(self):
        game=Path('/Games/Creeper World 3');exe=str(game/'CW3.app/Contents/MacOS/CW3')
        rows='1 /sbin/launchd\n42 '+exe+' -arg\n43 '+exe+'Helper\n'
        with patch.object(session.subprocess,'run',return_value=subprocess.CompletedProcess([],0,rows,'')):
            self.assertEqual(session.process_rows(game),[42])
        with patch.object(session.subprocess,'run',side_effect=subprocess.CalledProcessError(1,[])):
            with self.assertRaises(subprocess.CalledProcessError):session.process_rows(game)
        with patch.object(session.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
            with self.assertRaises(RuntimeError):session.process_rows(game)

    def test_python_environment_tries_usable_candidates_without_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'bad';b=root/'good';a.touch();b.touch()
            def probe(command,**kwargs):
                return subprocess.CompletedProcess(command,1,'','missing') if command[0]==str(a) else subprocess.CompletedProcess(command,0,'{"python":"good","version":"3.12","packages":{}}','')
            with patch.object(env,'python_candidates',return_value=[str(a),str(b)]),patch.object(env.shutil,'which',return_value=None),patch.object(env.subprocess,'run',side_effect=probe):
                result=env.discover_python({},root)
            self.assertEqual(result['command'],[str(b)]);self.assertEqual(len(result['attempts']),1)

    def test_missing_managed_compiler_does_not_select_mcs_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'bin';folder.mkdir()
            (folder/'mono').touch();(folder/'mcs').touch()
            result=env.mono_config({'tool_paths':[str(folder)]})
            self.assertNotIn('mono_runtime',result);self.assertNotIn('mono_compiler',result)

    def test_run_source_never_touches_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=['dev.py','--session',str(Path(tmp)/'session.json'),'run','--kind','source','--python-only']
            with patch.object(sys,'argv',args),patch.object(env,'test_source',return_value={'python_checks':'passed'}) as checks,patch.object(session,'save'),patch.object(dev,'run_session') as desktop:
                dev.main()
            checks.assert_called_once();self.assertFalse(checks.call_args.kwargs['standalone']);desktop.assert_not_called()

    def test_display_probe_must_match_scene_and_contain_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            record,b,persist=self.fixture(Path(tmp));session.advance(record,persist,b,.01)
            record['phase']='checking';record['evidence']['display_probe']['result']={'scene':'Other','controls':[]}
            with self.assertRaisesRegex(RuntimeError,'MainMenu text'):session.advance(record,persist,b,.01)
            self.assertNotIn('display_probe',record['evidence'])

    def test_python_uv_fallback_is_offline_and_requirements_locked(self):
        with patch.object(env,'python_candidates',return_value=[]),patch.object(env.shutil,'which',return_value='/bin/uv'),patch.object(env.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{"python":"cached"}','')) as call:
            result=env.discover_python({})
        self.assertIn('--offline',result['command']);self.assertIn('--with-requirements',result['command'])
        self.assertNotIn('--upgrade',result['command'])


class DiagnosticExchangeTests(unittest.TestCase):
    def fixture(self,root):
        folder=root/'cw3-debug';folder.mkdir();(folder/'enabled.txt').write_text('hash\n')
        backend=session.NativeMac(dict(game=str(root/'game'),state=str(root)))
        return folder,backend,{'evidence':{}}

    def test_timeout_retains_id_and_resume_reads_same_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp))
            with patch.object(session.debug,'context',return_value=(None,folder,'hash')):
                with self.assertRaises(TimeoutError):b.exchange(record,'runtime_probe',lambda:None,.001)
                ident=record['request']['id'];self.assertTrue((folder/'request.txt').exists())
                (folder/'request.txt').unlink()
                (folder/'response.json').write_text(json.dumps({'id':ident,'ok':True,'result':{'scene':'MainMenu'}}))
                self.assertEqual(b.exchange(record,'runtime_probe',lambda:None,.01),{'scene':'MainMenu'})
                self.assertFalse((folder/'request.txt').exists());self.assertNotIn('request',record)

    def test_retry_only_owned_readonly_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp));record['state']=str(folder.parent)
            record['request']={'id':'ours','command':'runtime_probe','submitted':True}
            (folder/'request.txt').write_text('ours\truntime_probe\n')
            session.retry_probe(record)
            self.assertNotIn('request',record);self.assertFalse((folder/'request.txt').exists())
            record['request']={'id':'ours','command':'quit','submitted':True}
            with self.assertRaises(ValueError):session.retry_probe(record)
            record['request']['command']='runtime_probe';(folder/'request.txt').write_text('another\truntime_probe\n')
            with self.assertRaises(RuntimeError):session.retry_probe(record)
            self.assertTrue((folder/'request.txt').exists())

    def test_stale_response_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp));(folder/'response.json').write_text('{"id":"old","ok":true}')
            with patch.object(session.debug,'context',return_value=(None,folder,'hash')):
                with self.assertRaises(TimeoutError):b.exchange(record,'runtime_probe',lambda:None,.001)
            self.assertNotIn('runtime_probe',record['evidence'])

    def test_other_pending_request_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp));request=folder/'request.txt';request.write_text('other\tquit\n')
            with patch.object(session.debug,'context',return_value=(None,folder,'hash')):
                with self.assertRaisesRegex(RuntimeError,'Another'):b.exchange(record,'runtime_probe',lambda:None,.01)
            self.assertEqual(request.read_text(),'other\tquit\n')


if __name__=='__main__':unittest.main()
