"""Enforce the public PR / private input trust boundary without credentials."""
from pathlib import Path
import copy
import re
import shlex
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from ci_build import package_stem
from ci_source import SOURCE_REPO, WORKFLOW, authorize


def workflow(name):
    # BaseLoader retains GitHub's `on` key instead of YAML 1.1's boolean spelling.
    return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)


def scalar_fields(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from scalar_fields(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scalar_fields(child, path + (index,))
    else:
        yield path, value


def commands(step):
    return [shlex.split(line) for line in step.get('run', '').replace('\\\n', ' ').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def command_step(steps, prefix):
    matches = [index for index, step in enumerate(steps)
               if any(tokens[:len(prefix)] == prefix for tokens in commands(step))]
    if len(matches) != 1:
        raise AssertionError('Expected one command step: ' + repr(prefix))
    return matches[0]


class WorkflowBoundary(unittest.TestCase):
    def assert_common(self, value):
        self.assertEqual(value['permissions'], {'contents': 'read'})
        for job in value['jobs'].values():
            self.assertEqual(job.get('permissions', value['permissions']), {'contents': 'read'})
            for step in job['steps']:
                action = step.get('uses', '')
                self.assertFalse(action.startswith(('actions/cache@', 'actions/cache/')))
                if action.startswith('actions/checkout@'):
                    self.assertEqual(step['with']['persist-credentials'], 'false')

    def assert_credentials(self, value, allowed=()):
        sensitive = []
        for path, field in scalar_fields(value):
            if path[-1] in ('GH_TOKEN', 'GITHUB_TOKEN') or isinstance(field, str) and re.search(r'secrets\.|github\.token|\b(?:GH_TOKEN|GITHUB_TOKEN)\b', field):
                sensitive.append(path)
        self.assertEqual(sensitive, list(allowed))

    def assert_pr(self, value):
        self.assert_common(value)
        self.assertEqual(set(value['on']), {'pull_request', 'push'})
        self.assertEqual(value['on']['push']['branches'], ['main'])
        self.assert_credentials(value)
        self.assertEqual(set(value['jobs']), {'check'})
        job = value['jobs']['check']
        self.assertNotIn('environment', job)
        for step in job['steps']:
            if 'uses' in step:
                self.assertTrue(step['uses'].startswith(('actions/checkout@', 'actions/setup-python@')))
            for tokens in commands(step):
                self.assertFalse(any(name in token for token in tokens for name in ('ci_inputs.py', 'ci_build.py', 'build_candidate.py')))
        for prefix in (['python', 'tools/workflow.py', 'check'],
                       ['python', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       ['python', 'tools/test.py', '--standalone']):
            command_step(job['steps'], prefix)

    def assert_build(self, value):
        self.assert_common(value)
        self.assertEqual(set(value['on']), {'workflow_dispatch'})
        self.assertEqual(set(value['on']['workflow_dispatch']['inputs']), {'version', 'target'})
        self.assertEqual(set(value['jobs']), {'build'})
        job = value['jobs']['build'];steps = job['steps']
        self.assertEqual(job['environment'], 'build-inputs')
        conditions = {}
        for clause in re.split(r'\s*&&\s*', job['if']):
            match = re.fullmatch(r"\s*(github\.\w+)\s*==\s*'([^']+)'\s*", clause)
            self.assertIsNotNone(match)
            self.assertNotIn(match[1], conditions)
            conditions[match[1]] = match[2]
        self.assertEqual(conditions, dict(zip(
            ('github.repository', 'github.event_name', 'github.actor', 'github.triggering_actor'),
            (SOURCE_REPO, 'workflow_dispatch', 'm1m0ry', 'm1m0ry'))))
        checkout = [s for s in steps if s.get('uses', '').startswith('actions/checkout@')]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(checkout[0]['with']['ref'], '${{ github.sha }}')
        authorize_at = command_step(steps, ['python3', 'tools/ci_source.py'])
        fetch_at = command_step(steps, ['python', 'tools/ci_inputs.py'])
        dependencies_at = command_step(steps, ['python', '-m', 'pip', 'install'])
        build_at = command_step(steps, ['python', 'tools/ci_build.py'])
        self.assertLess(authorize_at, fetch_at);self.assertLess(fetch_at, dependencies_at);self.assertLess(dependencies_at, build_at)
        self.assertNotIn('if', steps[authorize_at]);self.assertNotIn('if', steps[fetch_at])
        self.assertEqual(steps[fetch_at]['id'], 'inputs')
        self.assertEqual(steps[fetch_at].get('env', {}).get('GH_TOKEN'), '${{ secrets.CW3_INPUTS_READ_TOKEN }}')
        self.assert_credentials(value, [('jobs', 'build', 'steps', fetch_at, 'env', 'GH_TOKEN')])
        self.assertEqual(steps[build_at]['env']['INPUTS_SHA'], '${{ steps.inputs.outputs.sha256 }}')
        self.assertEqual(steps[build_at]['env']['BUILD_TARGET'], '${{ inputs.target }}')
        self.assertEqual(steps[build_at]['env']['BUILD_VERSION'], '${{ inputs.version }}')
        self.assertEqual(steps[build_at]['id'], 'package')
        build_command = commands(steps[build_at])[0]
        for flag, expected in [('--source-commit', '$GITHUB_SHA'), ('--target', '$BUILD_TARGET'),
                               ('--tag', '$BUILD_VERSION'), ('--inputs-sha256', '$INPUTS_SHA')]:
            self.assertEqual(build_command[build_command.index(flag)+1], expected)
        redirect_at = build_command.index('>')
        self.assertEqual(build_command[redirect_at:redirect_at+3], ['>', 'local-only/ci-build.log', '2>&1'])
        uploads = [s for s in steps if s.get('uses', '').startswith('actions/upload-artifact@')]
        self.assertEqual(len(uploads), 1)
        upload = uploads[0]['with']
        self.assertEqual(upload['path'].splitlines(), [
            'local-only/ci-release/${{ steps.package.outputs.archive }}',
            'local-only/ci-release/SHA256SUMS.txt', 'local-only/ci-release/build-info.json'])
        self.assertEqual(upload['if-no-files-found'], 'error');self.assertEqual(upload['retention-days'], '14')

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
        self.assert_pr(workflow('ci.yml'))

    def test_secret_precedes_dependencies_and_only_three_outputs_are_uploaded(self):
        self.assert_build(workflow('build.yml'))

    def test_unsafe_scopes_fail_even_when_the_original_text_is_still_present(self):
        build = workflow('build.yml')
        cases = []
        moved = copy.deepcopy(build);steps = moved['jobs']['build']['steps'];fetch = command_step(steps, ['python', 'tools/ci_inputs.py'])
        moved['jobs']['build']['env'] = {'GH_TOKEN': steps[fetch]['env'].pop('GH_TOKEN')};cases.append(moved)
        early = copy.deepcopy(build);steps = early['jobs']['build']['steps'];fetch = command_step(steps, ['python', 'tools/ci_inputs.py']);deps = command_step(steps, ['python', '-m', 'pip', 'install']);steps[fetch], steps[deps] = steps[deps], steps[fetch];cases.append(early)
        logs = copy.deepcopy(build)
        upload = next(step for step in logs['jobs']['build']['steps'] if step.get('uses', '').startswith('actions/upload-artifact@'))
        upload['with']['path'] += '\nlocal-only/ci-build.log';cases.append(logs)
        guard = copy.deepcopy(build);guard['jobs']['build']['if'] += ' || true';cases.append(guard)
        for index, value in enumerate(cases):
            with self.subTest(build=index), self.assertRaises(AssertionError):self.assert_build(value)
        for key, field in [('env', {'GH_TOKEN': '${{ secrets.CW3_INPUTS_READ_TOKEN }}'}), ('environment', 'build-inputs')]:
            value = workflow('ci.yml');value['jobs']['check'][key] = field
            with self.subTest(pr=key), self.assertRaises(AssertionError):self.assert_pr(value)

    def test_package_names_follow_explicit_platform_without_repacking(self):
        self.assertEqual(package_stem('windows-steam-22453699', 'v12.14', 'windows'), 'CW3-Windows-v12.14')
        self.assertEqual(package_stem('macos-steam-22453699', 'v12.14', 'macos'), 'CW3-Mac-v12.14')
        with self.assertRaises(ValueError):package_stem('macos-steam-22453699', 'v12.14', 'windows')
        with self.assertRaises(ValueError):package_stem('unknown', 'v12.14', 'windows')
        with self.assertRaises(ValueError):package_stem('macos-steam-22453699', '../v12.14', 'macos')


if __name__ == '__main__':
    unittest.main()
