"""Failure diagnostics publish fixed fields, never exception text or raw output."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_build


class BuildSummary(unittest.TestCase):
    def test_subprocess_status_and_elapsed_time_without_raw_output(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name);summary = folder / 'summary';log = folder / 'private.log'
            with patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)), \
                 patch.object(ci_build.time, 'monotonic', side_effect=[100, 102.5]), \
                 log.open('w') as output, self.assertRaises(subprocess.CalledProcessError) as failed:
                with ci_build.build_stage('build'):
                    subprocess.run([sys.executable, '-c', "print('PRIVATE_INPUT_PATH_AND_TOKEN');raise SystemExit(19)"],
                                   stdout=output, stderr=output, check=True)
            self.assertEqual(failed.exception.returncode, 19)
            self.assertEqual(summary.read_text().splitlines(), [
                '| stage | exit_code | elapsed_seconds |', '| --- | ---: | ---: |', '| build | 19 | 2.500 |'])
            self.assertIn('PRIVATE_INPUT_PATH_AND_TOKEN', log.read_text())

    def test_success_adds_no_failure_summary(self):
        with tempfile.TemporaryDirectory() as name:
            summary = Path(name) / 'summary'
            with patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)):
                with ci_build.build_stage('verify'):
                    pass
                with self.assertRaises(ValueError):
                    with ci_build.build_stage('PRIVATE_INPUT_PATH\n| injected |'):
                        pass
            self.assertFalse(summary.exists())

    def test_main_identifies_each_failing_phase_without_disclosing_arguments(self):
        for failing in ci_build.STAGES:
            with self.subTest(stage=failing), tempfile.TemporaryDirectory() as name:
                root = Path(name);summary = root / 'summary';build = root / 'local-only/ci-build'
                secret = 'PRIVATE_INPUTS_AND_ERROR_TEXT'
                def plan(*args):
                    if failing == 'plan':raise ValueError(secret)
                    return dict(source_repo=ci_build.SOURCE_REPO, source_commit='a'*40,
                                source_dirty=False, version='v99.1', build_inputs_sha256='b'*64)
                def run(args, **kwargs):
                    script = Path(args[1]).stem
                    phase = dict(independent='build', package_player='package', verify_package='verify')[script]
                    if phase == failing:raise subprocess.CalledProcessError(17, args, stderr=secret)
                    if phase == 'build':
                        build.mkdir(parents=True);(build/'manifest.json').write_text(json.dumps(dict(target_id='windows-steam-22453699')))
                    elif phase == 'package':
                        package = Path(args[-1]);package.mkdir()
                        (package/'manifest.json').write_text(json.dumps(dict(target_id='windows-steam-22453699', files=[])))
                        Path(str(package)+'.zip').write_bytes(b'fixture')
                    elif failing == 'provenance':
                        (root/'local-only/ci-release/SHA256SUMS.txt').mkdir()
                argv = ['ci_build.py', '--config', str(root/secret), '--tag', 'v99.1', '--target', 'windows',
                        '--source-commit', 'a'*40, '--inputs-sha256', 'b'*64]
                with patch.object(ci_build, 'ROOT', root), patch.object(ci_build, 'plan', side_effect=plan), \
                     patch.object(ci_build.subprocess, 'run', side_effect=run), patch.object(sys, 'argv', argv), \
                     patch.dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)), \
                     self.assertRaises((ValueError, OSError, subprocess.CalledProcessError)):
                    ci_build.main()
                fields = [v.strip() for v in summary.read_text().splitlines()[-1].split('|')[1:-1]]
                self.assertEqual(fields[:2], [failing, '17' if failing in ('build','package','verify') else '1'])
                self.assertGreaterEqual(float(fields[2]), 0)
                self.assertNotIn(secret, summary.read_text())
                self.assertNotIn(str(root), summary.read_text())


if __name__ == '__main__':
    unittest.main()
