"""Candidate command through a fake gh process and complete synthetic ZIPs."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_player import INSTRUCTION_SOURCES, PLAYER_SOURCES, instructions, target_description
from player_install import ADDED, PAYLOAD, target_identity

VERSION = 'v12.14'
FAKE_GH = '''import base64,json,os,shutil,sys
from pathlib import Path
args=sys.argv[1:];root=Path(os.environ['CANDIDATE_FIXTURE']);run_id=int(os.environ.get('FAKE_RUN_ID','101'));case=os.environ.get('FAKE_CASE','ok');target=os.environ.get('FAKE_TARGET','windows');ref=os.environ.get('FAKE_REF','feature/native-mac');commit=os.environ['FAKE_COMMIT']
calls=root/('calls-'+str(run_id)+'.jsonl')
with calls.open('a') as f:f.write(json.dumps(args)+'\\n')
if args[0]=='api':
 endpoint=next(a for a in args if a.startswith('repos/'))
 assert endpoint.startswith('repos/m1m0ry/cw3-localization-public/')
 if endpoint.endswith('/dispatches'):
  assert endpoint.endswith('/workflows/build.yml/dispatches')
  assert json.load(sys.stdin)=={'ref':ref,'inputs':{'version':'v12.14','target':target}}
  if case=='empty_response':raise SystemExit(0)
  result={} if case=='missing_id' else {'workflow_run_id':run_id}
 elif endpoint.endswith('/actions/runs/'+str(run_id)):
  result={'id':run_id,'path':'.github/workflows/build.yml','head_branch':ref,'event':'workflow_dispatch','conclusion':'success','head_sha':commit,'repository':{'full_name':'m1m0ry/cw3-localization-public'}}
  if case=='different_commit':result['head_sha']='b'*40
  if case=='wrong_run':result['head_branch']='other'
  if case=='wrong_repo':result['repository']['full_name']='fork/repository'
  if case=='moving_run' and any(json.loads(line)[:2]==['run','watch'] for line in calls.read_text().splitlines()):result['head_sha']='b'*40
 elif endpoint.endswith('/contents/resources/ci-inputs.json?ref='+commit):
  result={'content':base64.b64encode(json.dumps({'targets':{'windows':{'sha256':'c'*64},'macos':{'sha256':'d'*64}}}).encode()).decode()}
 else:raise SystemExit('Unexpected endpoint: '+endpoint)
 print(json.dumps(result))
elif args[:2]==['run','watch']:
 assert args[2]==str(run_id)
 if case=='failed':raise SystemExit(1)
 if case=='local_change':
  (root/'tools/player_install.py').write_text('changed while waiting')
  for name in ('使用说明-Windows.txt','使用说明-Mac.txt'):(root/'player'/name).write_text('later instructions')
  for name in ('supported-build.json','macos-target.json'):(root/'resources'/name).write_text('{}')
 if case=='branch_moves':
  (root/'tools/player_install.py').write_text('later branch source')
  import subprocess
  subprocess.run(['git','add','tools/player_install.py'],cwd=root,check=True)
  subprocess.run(['git','commit','-qm','later branch commit'],cwd=root,check=True)
elif args[:2]==['run','download']:
 assert args[2]==str(run_id) and args[args.index('-n')+1]=='cw3-package-'+commit+'-'+target
 destination=Path(args[args.index('-D')+1])
 for p in (root/'artifact').iterdir():
  shutil.copy2(p,destination/p.name)
  if case=='download_failed':raise SystemExit(1)
else:raise SystemExit('Unexpected gh command')
'''


class CandidateCommand(unittest.TestCase):
    def fixture(self, root, corruption=None, target='windows'):
        for name in set(PLAYER_SOURCES.values()) | set(INSTRUCTION_SOURCES.values()) | {
                '.gitattributes',
                'tools/build_candidate.py', 'tools/ci_inputs.py', 'tools/ci_source.py',
                'tools/package_player.py', 'tools/verify_package.py',
                'resources/supported-build.json', 'resources/macos-target.json'}:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        git('init', '-b', 'feature/native-mac')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'core.fsmonitor', 'false')
        git('add', '.')
        git('commit', '-m', 'Source snapshot')
        commit = git('rev-parse', 'HEAD')
        binary = root / 'bin'
        binary.mkdir()
        gh = binary / 'gh'
        gh.write_text('#!' + sys.executable + '\n' + FAKE_GH)
        gh.chmod(0o755)
        artifact = root / 'artifact'
        artifact.mkdir()
        digest = lambda data: hashlib.sha256(data).hexdigest()
        name = ('CW3-Windows-' if target == 'windows' else 'CW3-Mac-') + VERSION + '.zip'
        payload = PAYLOAD if target == 'macos' else PAYLOAD - {ADDED}
        files = {file: b'synthetic payload: ' + file.encode() for file in sorted(payload)}
        if corruption == 'extra_payload':files['CW3_Data/Managed/CW3Debug.dll'] = b'debug fixture'
        rows = [dict(file=file, before=None, after=digest(data), bytes=len(data)) for file, data in files.items()]
        provenance = dict(source_repo='m1m0ry/cw3-localization-public', source_commit=commit,
                          source_dirty=False, version=VERSION, build_inputs_sha256=('c' if target == 'windows' else 'd') * 64)
        if corruption in ('source_commit', 'build_inputs_sha256'):
            provenance[corruption] = 'e' * len(provenance[corruption])
        if corruption in ('source_dirty', 'source_dirty_number'):
            provenance['source_dirty'] = True if corruption == 'source_dirty' else 0
        profile = 'macos-target.json' if target == 'macos' else 'supported-build.json'
        supported = json.loads((ROOT / 'resources' / profile).read_text())
        identity = target_identity(supported)
        if corruption == 'target_id':identity['target_id'] = 'other-steam-22453699'
        if corruption == 'platform':identity['platform'] = 99
        manifest = json.dumps(dict(provenance, **identity, format=2, target=target_description(supported),
                                   files=rows)).encode()
        controls = {dest: (ROOT / source).read_bytes() for dest, source in PLAYER_SOURCES.items()}
        controls['使用说明.txt'] = instructions(supported, VERSION).encode()
        controls['manifest.json'] = manifest
        if corruption == 'installer':controls['install.py'] = b'modified installer'
        if corruption == 'instructions':controls['使用说明.txt'] = b'obsolete instructions with internally consistent ZIP hashes'
        if corruption == 'extra_file':controls['private-input.bin'] = b'extra fixture'
        if corruption == 'payload_bytes':files[rows[0]['file']] += b'changed'
        with zipfile.ZipFile(artifact / name, 'w') as archive:
            for file, data in {**files, **controls}.items():
                archive.writestr(name.removesuffix('.zip') + '/' + file, data)
        archive_sha = digest((artifact / name).read_bytes())
        info = dict(provenance, target_id=identity['target_id'], archive=name, archive_sha256=archive_sha,
                    manifest_sha256=digest(manifest), payload_sha256={row['file']: row['after'] for row in rows})
        if corruption == 'zip_sha':info['archive_sha256'] = '0' * 64
        (artifact / 'build-info.json').write_text(json.dumps(info))
        (artifact / 'SHA256SUMS.txt').write_text(archive_sha + '  ' + name + '\n')
        return dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                    CANDIDATE_FIXTURE=str(root), FAKE_TARGET=target, FAKE_COMMIT=commit)

    def command(self, root, env, extra=()):
        return subprocess.run([sys.executable, str(root / 'tools/build_candidate.py'), '--ref', env.get('FAKE_REF', 'feature/native-mac'), '--version', VERSION,
                               '--target', env['FAKE_TARGET'], *extra], env=env, capture_output=True, text=True)

    def test_concurrent_requests_keep_their_exact_run_and_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = self.fixture(root)
            with concurrent.futures.ThreadPoolExecutor(2) as executor:
                results = list(executor.map(lambda n: self.command(root, dict(env, FAKE_RUN_ID=str(n))), (101, 102)))
            for number, result in zip((101, 102), results):
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('/actions/runs/' + str(number), result.stdout)
                self.assertTrue((root / ('local-only/candidate-' + str(number)) / ('CW3-Windows-' + VERSION + '.zip')).is_file())
                calls = [json.loads(line) for line in (root / ('calls-' + str(number) + '.jsonl')).read_text().splitlines()]
                self.assertEqual([call[2] for call in calls if call[:2] == ['run', 'download']], [str(number)])

    def test_failed_ambiguous_or_changed_run_never_downloads_or_redispatches(self):
        for case in ('failed', 'missing_id', 'empty_response', 'wrong_run', 'wrong_repo', 'moving_run', 'different_commit'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                env = self.fixture(root)
                result = self.command(root, dict(env, FAKE_CASE=case))
                self.assertNotEqual(result.returncode, 0)
                calls = [json.loads(line) for line in (root / 'calls-101.jsonl').read_text().splitlines()]
                self.assertFalse(any(call[:2] == ['run', 'download'] for call in calls))
                self.assertEqual(sum(any('/dispatches' in arg for arg in call) for call in calls), 1)

    def test_frozen_run_source_survives_local_edits_and_branch_advancement(self):
        for target in ('windows', 'macos'):
            for case in ('local_change', 'branch_moves'):
                with self.subTest(target=target, case=case), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder); env = self.fixture(root, target=target)
                    result = self.command(root, dict(env, FAKE_CASE=case))
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('PASS candidate', result.stdout)
                    self.assertTrue((root/'local-only/candidate-101').is_dir())

    def test_dirty_client_is_rejected_before_dispatch_or_output_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); env = self.fixture(root)
            (root/'player/使用说明-Windows.txt').write_text('uncommitted instructions')
            result = self.command(root, env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('exact clean source commit', result.stderr)
            self.assertFalse((root/'calls-101.jsonl').exists())
            self.assertFalse((root/'local-only/candidate-101').exists())

    def test_corrupt_provenance_payload_and_installer_are_rejected_and_removed(self):
        for corruption in ('source_commit', 'source_dirty', 'source_dirty_number', 'build_inputs_sha256',
                           'zip_sha', 'target_id', 'platform', 'extra_payload', 'extra_file', 'installer', 'payload_bytes'):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                env = self.fixture(root, corruption)
                result = self.command(root, env)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('PASS candidate', result.stdout)
                self.assertFalse((root / 'local-only/candidate-101').exists())

    def test_obsolete_instructions_are_rejected_for_both_targets(self):
        for target in ('windows','macos'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);env=self.fixture(root,'instructions',target)
                result=self.command(root,env)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Player instructions differ',result.stderr)
                self.assertFalse((root/'local-only/candidate-101').exists())

    def test_mac_uses_its_own_input_hash_and_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = self.fixture(root, target='macos')
            result = self.command(root, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / 'local-only/candidate-101'/('CW3-Mac-' + VERSION + '.zip')).is_file())
            self.assertIn('cw3-package-' + env['FAKE_COMMIT'] + '-macos', (root / 'calls-101.jsonl').read_text())

    def test_tag_dispatch_uses_native_ref_and_pins_its_actual_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = dict(self.fixture(root), FAKE_REF='candidate-v12.14')
            result = self.command(root, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Pinned source: candidate-v12.14 -> ' + env['FAKE_COMMIT'], result.stdout)

    def test_partial_download_preserves_other_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = self.fixture(root)
            keep = root / 'local-only/older'
            keep.mkdir(parents=True)
            (keep / 'unique').write_bytes(b'keep')
            result = self.command(root, dict(env, FAKE_CASE='download_failed'))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'local-only/candidate-101').exists())
            self.assertEqual((keep / 'unique').read_bytes(), b'keep')

    def test_arbitrary_source_and_existing_output_fail_before_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = self.fixture(root)
            existing = root / 'local-only/existing'
            existing.mkdir(parents=True)
            (existing / 'keep').write_bytes(b'keep')
            for ref, extra in [('refs/pull/8/head', ()), ('fork:topic', ()), ('feature/native-mac', ('--output', str(existing)))]:
                result = self.command(root, dict(env, FAKE_REF=ref), extra)
                self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / 'calls-101.jsonl').exists())
            self.assertEqual((existing / 'keep').read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
