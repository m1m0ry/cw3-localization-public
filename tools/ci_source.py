"""Gate the dispatched repository ref before a manual build reads private inputs."""
from pathlib import Path
import argparse
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO = 'm1m0ry/cw3-localization-public'
WORKFLOW = '.github/workflows/build.yml'


def validate_ref_name(ref):
    if (not ref or ref.startswith('refs/') or
            subprocess.run(['git', 'check-ref-format', '--branch', ref],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode):
        raise ValueError('Select a branch or tag name in the fixed repository')


def authorize(env):
    ref = env.get('GITHUB_REF', '')
    prefix = next((prefix for prefix in ('refs/heads/', 'refs/tags/') if ref.startswith(prefix)), None)
    if prefix is None:
        raise ValueError('Only a repository branch or tag may receive a manual dispatch')
    validate_ref_name(ref[len(prefix):])
    expected = dict(GITHUB_REPOSITORY=SOURCE_REPO, GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_ACTOR='m1m0ry', GITHUB_TRIGGERING_ACTOR='m1m0ry',
                    GITHUB_WORKFLOW_REF=SOURCE_REPO + '/' + WORKFLOW + '@' + ref)
    if any(env.get(key) != value for key, value in expected.items()):
        raise ValueError('Only the owner may dispatch or rerun this repository build workflow')


def verify_checkout(root, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a full lowercase source commit SHA')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    if git('rev-parse', 'HEAD') != commit or git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Build requires the exact clean source commit')


def validate_version(version):
    if not re.fullmatch(r'v\d+\.\d+(?:\.\d+)?', version):
        raise ValueError('Expected a version such as v12.14')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    authorize(os.environ)
    validate_version(args.version)
    verify_checkout(ROOT, os.environ.get('GITHUB_SHA', ''))
    print('Authorized source:', os.environ['GITHUB_REF'], os.environ['GITHUB_SHA'])


if __name__ == '__main__':
    main()
