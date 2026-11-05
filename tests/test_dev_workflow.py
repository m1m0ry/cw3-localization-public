"""Maintenance orchestration tests use isolated files and fake desktop operations only."""
from pathlib import Path
import json
import shutil
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
from player_fixture import fixture, macho, sha, snapshot


def full_package(root):
    game, package, manifest = fixture(root, native=True)
    registry = session.player.read(package / session.REGISTRY)
    registry['runtime_sha256'] = session.player.digest(package / session.RUNTIME)
    update_payload(package, manifest, session.REGISTRY, json.dumps(registry).encode())
    return game, package, manifest


def update_payload(package, manifest, name, content):
    (package / name).write_bytes(content)
    next(row for row in manifest['files'] if row['file'] == name).update(after=sha(content), bytes=len(content))
    session.save(package / 'manifest.json', manifest)


class FakeDesktop:
    def __init__(self, root):
        self.game=root/'game';self.state=root/'state';self.events=[];self.running=[];self.timeout_once=False
        self.capture=root/'screen.png'
    def processes(self):return self.running
    def quit(self,timeout):self.events.append('quit');self.running=[]
    def install(self,package,manifest):
        self.events.append('install')
        for row in manifest['files']:
            target=session.player.installed_path(self.game,row['file'],manifest)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(package/row['file'],target)
    def enable(self):self.events.append('enable')
    def launch(self):self.events.append('launch');self.running=[77]
    def exchange(self,record,command,persist,timeout):
        self.events.append(command)
        if self.timeout_once:self.timeout_once=False;raise TimeoutError('waiting')
        result={'scene':'MainMenu','controls':[{'text':'开始'}],'rendering_abi':'v1','renderer_assembly':'CW3ExternalRuntime','rendering_bound':True}
        if command=='screenshot':self.capture.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB`\x82');result={'path':str(self.capture),'queued':True}
        record['evidence'][command]={'ok':True,'result':result};persist();return result


class WorkflowTests(unittest.TestCase):
    def fixture(self,root):
        _,package,_=full_package(root)
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
            (Path(record['package'])/session.RUNTIME).write_bytes(b'other')
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

    def test_retry_unwritten_screenshot_keeps_install_launch_and_other_evidence(self):
        for content in (None,b'partial PNG'):
            with self.subTest(content=content),tempfile.TemporaryDirectory() as tmp:
                record,b,persist=self.fixture(Path(tmp));session.advance(record,persist,b,.01)
                b.capture.unlink()
                if content is not None:b.capture.write_bytes(content)
                record['phase']='checking';evidence=record['evidence'].copy()
                session.retry_probe(record)
                self.assertNotIn('screenshot',record['evidence'])
                self.assertEqual(record['evidence']['runtime_probe'],evidence['runtime_probe'])
                self.assertEqual(record['evidence']['display_probe'],evidence['display_probe'])
                session.advance(record,persist,b,.01)
                self.assertEqual(record['phase'],'verified')
                self.assertEqual(b.events.count('screenshot'),2)
                for event in ('quit','install','launch','runtime_probe','display_probe'):
                    self.assertEqual(b.events.count(event),1)
                session.retry_probe(record)
                self.assertIn('screenshot',record['evidence'])

    def test_matching_marker_with_old_command_blocks_launch(self):
        for command in ('quit','settings_save'):
            with self.subTest(command=command),tempfile.TemporaryDirectory() as tmp:
                record,b,persist=self.fixture(Path(tmp))
                folder=b.state/'cw3-debug';folder.mkdir(parents=True)
                marker=folder/'enabled.txt';marker.write_text('current-hash')
                request=folder/'request.txt';request.write_text('old-id\t'+command+'\n')
                native=session.NativeMac(record)
                with patch.object(session.debug,'context',return_value=(None,folder,'current-hash')),patch.object(b,'enable',side_effect=native.enable),patch.object(session.debug,'action') as action:
                    with self.assertRaisesRegex(RuntimeError,'outstanding'):session.advance(record,persist,b,.01)
                    action.assert_not_called()
                self.assertNotIn('launch',b.events)
                self.assertEqual(marker.read_text(),'current-hash')
                self.assertEqual(request.read_text(),'old-id\t'+command+'\n')

    def test_scope_selects_only_supported_incremental_route(self):
        self.assertEqual(dev.classify([]),'none')
        self.assertEqual(dev.classify(['tools/independent.py','tests/test_any.py']),'source')
        self.assertEqual(dev.classify(['src/rendering/CW3Rendering.cs','tests/RenderingCacheContracts.cs']),'rendering')
        self.assertEqual(dev.classify(['src/runtime/RuntimePaths.cs']),'package')
        self.assertEqual(dev.classify(['src/rendering/CW3RenderingBridge.cs']),'package')
        self.assertEqual(dev.classify(['src/rendering/CW3Rendering.cs','resources/layout.json']),'package')

    def test_main_menu_alone_does_not_verify_external_renderer(self):
        for field,value in (('rendering_abi','v0'),('renderer_assembly','CW3Rendering'),('rendering_bound',False)):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                record,b,persist=self.fixture(Path(tmp));session.advance(record,persist,b,.01)
                record['phase']='checking';record['evidence']['runtime_probe']['result'][field]=value
                with self.assertRaisesRegex(RuntimeError,'external rendering bridge'):session.advance(record,persist,b,.01)
                self.assertNotIn('runtime_probe',record['evidence']);self.assertNotEqual(record['phase'],'verified')

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


class ExternalRenderingWorkflowTests(unittest.TestCase):
    def test_legacy_single_dll_package_is_rejected_before_game_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'old';package.mkdir()
            (package/'CW3Rendering.dll').write_bytes(b'old renderer')
            session.save(package/'manifest.json',dict(format=1,kind='rendering_component',target_id=session.game_target.MACOS,sha256=sha(b'old renderer')))
            with self.assertRaisesRegex(ValueError,'stable bridge'):
                session.new_session(dict(game=str(root/'game'),state=str(root/'state')),package)
            self.assertFalse((root/'game').exists())

    def test_registry_and_external_runtime_must_match_before_quit(self):
        with tempfile.TemporaryDirectory() as tmp:
            game,package,manifest=full_package(Path(tmp));before=snapshot(game)
            # Individually valid manifest hashes still cannot authorize a mismatched pair.
            update_payload(package,manifest,session.RUNTIME,b'another build')
            with self.assertRaisesRegex(ValueError,'same build'):
                session.new_session(dict(game=str(game),state=str(game/'state')),package)
            self.assertEqual(snapshot(game),before)

    def test_build_rendering_uses_exact_cloud_candidate(self):
        with patch.object(sys,'argv',['dev.py','build','--kind','rendering','--ref','feature/external','--version','v12.15']),patch.object(dev,'cloud_build',return_value=Path('candidate')) as build:
            dev.main()
        build.assert_called_once_with('feature/external','v12.15','macos')

    def test_rendering_requires_ref_before_tests_or_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            for action in ('build','run'):
                with self.subTest(action=action),patch.object(sys,'argv',['dev.py','--session',str(Path(tmp)/'session'),action,'--kind','rendering']),patch.object(dev,'desktop_lock',return_value=dev.nullcontext()),patch.object(env,'test_source') as checks,patch.object(dev,'cloud_build') as build:
                    with self.assertRaises(SystemExit):dev.main()
                    checks.assert_not_called();build.assert_not_called()

    def test_run_auto_rendering_uses_full_package_and_saves_previous_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,package,manifest=full_package(root)
            old=game/session.RUNTIME;old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(b'previous runtime')
            config=root/'config.json';session.save(config,dict(game=str(game),state=str(root/'state')))
            args=['dev.py','--config',str(config),'--session',str(root/'session.json'),'run','--ref','feature/external','--version','v12.15']
            with patch.object(sys,'argv',args),patch.object(dev,'desktop_lock',return_value=dev.nullcontext()),patch.object(dev,'changed_paths',return_value=['src/rendering/CW3Rendering.cs']),patch.object(env,'test_source',return_value={'python_checks':'passed'}),patch.object(dev,'cloud_build',return_value=root/'download') as build,patch.object(dev,'unpack_candidate',return_value=package),patch.object(dev,'run_session',side_effect=lambda path,record,timeout:record) as run,patch.object(dev,'ROOT',root):
                dev.main()
            build.assert_called_once_with('feature/external','v12.15','macos')
            record=run.call_args.args[1]
            self.assertEqual(record['previous_runtime_sha256'],sha(b'previous runtime'))
            self.assertEqual(set(session.wanted_hashes(manifest)),session.player.PAYLOAD)

    def test_native_install_updates_external_pair_without_touching_bridge_or_signing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,package,manifest=full_package(root)
            backend=session.NativeMac(dict(game=str(game),state=str(root/'state')))
            player=session.player
            with patch.dict(player.FINGERPRINTS,{player.MACOS:sha(macho())}),patch.object(player,'idle'),patch.object(player.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')),patch.object(player,'signing') as sign:
                # First migration uses the real installer and needs a bundle signature.
                backend.install(package,manifest);sign.assert_called_once();sign.reset_mock()
                before=snapshot(game)
                bridges={name:player.installed_path(game,name,manifest).stat().st_mtime_ns for name in ('CW3_Data/Managed/CW3Rendering.dll','CW3_Data/Managed/CW3Runtime.dll')}
                update_payload(package,manifest,session.RUNTIME,b'updated external renderer')
                registry=player.read(package/session.REGISTRY);registry['runtime_sha256']=sha(b'updated external renderer')
                update_payload(package,manifest,session.REGISTRY,json.dumps(registry).encode())
                session.package_identity(package)
                backend.install(package,manifest)
                after=snapshot(game)
                self.assertEqual({name for name in before if before[name]!=after[name]}, {session.RUNTIME,session.REGISTRY})
                for name,stamp in bridges.items():self.assertEqual(player.installed_path(game,name,manifest).stat().st_mtime_ns,stamp)
                self.assertEqual(session.installed_hashes(game,manifest),session.wanted_hashes(manifest))
                sign.assert_not_called()

    def test_known_previous_diagnostics_marker_refreshes_to_updated_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,package,manifest=full_package(root)
            # Isolated installed bytes; no process, launcher or real game is involved.
            FakeDesktop(root).install(package,manifest)
            state=root/'CW3Localization';folder=state/'cw3-debug';folder.mkdir(parents=True)
            (state/'font-status.json').write_text('{}')
            old=sha(b'old runtime');marker=folder/'enabled.txt';marker.write_text(old+'\n')
            backend=session.NativeMac(dict(game=str(game),state=str(state),previous_runtime_sha256=old))
            with patch.object(session.player,'idle'):
                backend.enable();backend.enable()
            self.assertEqual(marker.read_text().strip(),session.player.digest(game/session.RUNTIME))

    def test_unknown_marker_or_pending_request_is_not_overwritten(self):
        for pending in (False,True):
            with self.subTest(pending=pending),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);folder=root/'debug';folder.mkdir();marker=folder/'enabled.txt';marker.write_text('old')
                if pending:(folder/'request.txt').write_text('someone\truntime_probe\n')
                backend=session.NativeMac(dict(game=str(root/'game'),state=str(root/'state'),previous_runtime_sha256='old' if pending else 'different'))
                with patch.object(session.debug,'context',return_value=(None,folder,'new')),patch.object(session.debug,'action') as action:
                    with self.assertRaises(RuntimeError):backend.enable()
                    action.assert_not_called()
                self.assertEqual(marker.read_text(),'old')


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

    def test_queued_screenshot_timeout_can_request_a_new_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp));record['state']=str(folder.parent)
            capture=folder/'never-written.png'
            def queued(predicate,timeout,message):
                if not record.get('request'):raise TimeoutError('PNG was not written')
                ident=record['request']['id'];(folder/'request.txt').unlink()
                return {'id':ident,'ok':True,'result':{'queued':True,'path':str(capture)}}
            with patch.object(session.debug,'context',return_value=(None,folder,'hash')),patch.object(session,'wait_until',side_effect=queued):
                with self.assertRaises(TimeoutError):b.exchange(record,'screenshot',lambda:None,.001)
            old_id=record['evidence']['screenshot']['id']
            self.assertNotIn('request',record)
            session.retry_probe(record)
            self.assertNotIn('screenshot',record['evidence'])
            def completed(predicate,timeout,message):
                if record.get('request'):
                    ident=record['request']['id'];(folder/'request.txt').unlink()
                    capture.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB`\x82')
                    return {'id':ident,'ok':True,'result':{'queued':True,'path':str(capture)}}
                return predicate()
            with patch.object(session.debug,'context',return_value=(None,folder,'hash')),patch.object(session,'wait_until',side_effect=completed):
                b.exchange(record,'screenshot',lambda:None,.001)
            self.assertNotEqual(record['evidence']['screenshot']['id'],old_id)
            self.assertTrue(session.complete_capture(capture))

    def test_capture_retry_preserves_foreign_pending_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,b,record=self.fixture(Path(tmp));record['state']=str(folder.parent)
            record['evidence']['screenshot']={'result':{'path':str(folder/'absent.png'),'queued':True}}
            request=folder/'request.txt';request.write_text('other\tquit\n')
            with self.assertRaisesRegex(RuntimeError,'different request'):session.retry_probe(record)
            self.assertIn('screenshot',record['evidence'])
            self.assertEqual(request.read_text(),'other\tquit\n')
            request.unlink();request.symlink_to(folder/'absent-request')
            with self.assertRaises(RuntimeError):session.retry_probe(record)
            self.assertTrue(request.is_symlink())

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
