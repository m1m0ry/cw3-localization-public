"""Enforce the public PR / private input trust boundary without credentials."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from ci_build import package_stem
from ci_source import SOURCE_REPO, WORKFLOW, authorize


class WorkflowBoundary(unittest.TestCase):
    def test_owner_can_dispatch_repository_development_branches_and_tags(self):
        for ref in ('refs/heads/main', 'refs/heads/feature/native-mac', 'refs/tags/candidate-v12.14'):
            env = dict(GITHUB_REPOSITORY=SOURCE_REPO, GITHUB_EVENT_NAME='workflow_dispatch',
                       GITHUB_REF=ref, GITHUB_ACTOR='m1m0ry', GITHUB_TRIGGERING_ACTOR='m1m0ry',
                       GITHUB_WORKFLOW_REF=SOURCE_REPO + '/' + WORKFLOW + '@' + ref)
            authorize(env)

    def test_fork_pr_unauthorized_actor_or_mismatched_workflow_cannot_authorize_inputs(self):
        env = dict(GITHUB_REPOSITORY=SOURCE_REPO, GITHUB_EVENT_NAME='workflow_dispatch',
                   GITHUB_REF='refs/heads/feature/native-mac', GITHUB_ACTOR='m1m0ry', GITHUB_TRIGGERING_ACTOR='m1m0ry',
                   GITHUB_WORKFLOW_REF=SOURCE_REPO + '/' + WORKFLOW + '@refs/heads/feature/native-mac')
        authorize(env)
        for key, value in [('GITHUB_REPOSITORY', 'fork/repository'), ('GITHUB_EVENT_NAME', 'pull_request'),
                           ('GITHUB_REF', 'refs/pull/8/head'), ('GITHUB_REF', 'refs/heads/../bad'),
                           ('GITHUB_ACTOR', 'contributor'), ('GITHUB_TRIGGERING_ACTOR', 'contributor'),
                           ('GITHUB_WORKFLOW_REF', SOURCE_REPO + '/' + WORKFLOW + '@refs/heads/topic')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                authorize(dict(env, **{key: value}))

    def test_pr_checks_have_no_input_credentials_or_build_artifacts(self):
        check = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('pull_request:', check)
        self.assertIn('python tools/workflow.py check', check)
        self.assertIn('python -m unittest discover -s tests -v', check)
        for forbidden in ('secrets.', 'environment:', 'ci_inputs.py', 'upload-artifact', 'actions/cache', 'pull_request_target', 'workflow_run:'):
            self.assertNotIn(forbidden, check)

    def test_secret_precedes_dependencies_and_only_three_outputs_are_uploaded(self):
        build = (ROOT / '.github/workflows/build.yml').read_text()
        self.assertIn('environment: build-inputs', build)
        self.assertNotIn("github.ref == 'refs/heads/main'", build)
        self.assertIn("github.event_name == 'workflow_dispatch'", build)
        self.assertIn("github.actor == 'm1m0ry'", build)
        self.assertIn("github.triggering_actor == 'm1m0ry'", build)
        self.assertIn('ref: ${{ github.sha }}', build)
        self.assertNotIn('source_ref', build)
        self.assertEqual(build.count('secrets.'), 1)
        self.assertEqual(build.count('GH_TOKEN:'), 1)
        prepared = build.index('python tools/ci_inputs.py')
        dependencies = build.index('python -m pip install')
        self.assertLess(build.index('python3 tools/ci_source.py'), prepared)
        self.assertLess(prepared, dependencies)
        self.assertNotIn('GH_TOKEN', build[dependencies:])
        self.assertNotIn('secrets.', build[dependencies:])
        self.assertIn('> local-only/ci-build.log 2>&1', build)
        self.assertIn('--target "$BUILD_TARGET" --inputs-sha256', build)
        upload = build[build.index('          path: |'):build.index('          if-no-files-found:')]
        self.assertEqual(upload.splitlines()[1:], [
            '            local-only/ci-release/${{ steps.package.outputs.archive }}',
            '            local-only/ci-release/SHA256SUMS.txt',
            '            local-only/ci-release/build-info.json'])
        for text in (build, (ROOT / '.github/workflows/ci.yml').read_text()):
            self.assertIn('contents: read', text)
            self.assertIn('persist-credentials: false', text)
            for forbidden in ('contents: write', 'actions/cache', 'pull_request_target', 'workflow_run:'):
                self.assertNotIn(forbidden, text)

    def test_package_names_follow_explicit_platform_without_repacking(self):
        self.assertEqual(package_stem('windows-steam-22453699', 'v12.14', 'windows'), 'CW3-Windows-v12.14')
        self.assertEqual(package_stem('macos-steam-22453699', 'v12.14', 'macos'), 'CW3-Mac-v12.14')
        with self.assertRaises(ValueError):package_stem('macos-steam-22453699', 'v12.14', 'windows')
        with self.assertRaises(ValueError):package_stem('unknown', 'v12.14', 'windows')
        with self.assertRaises(ValueError):package_stem('macos-steam-22453699', '../v12.14', 'macos')


if __name__ == '__main__':
    unittest.main()
