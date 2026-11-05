"""Select a verified existing interpreter, or an offline uv environment; never install globally."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ('UnityPy', 'fontTools', 'yaml', 'PIL', 'brotli')
PROBE = """import importlib, importlib.metadata as m, json, sys
assert sys.version_info >= (3, 10), 'Python 3.10 or newer required'
for name in %r: importlib.import_module(name)
print(json.dumps({'python': sys.executable, 'version': sys.version.split()[0],
 'packages': {n: m.version(n) for n in ('UnityPy','fonttools','PyYAML','Pillow','brotli')}}))
""" % (IMPORTS,)


def resolve_path(value, root=ROOT):
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def python_candidates(config, root=ROOT):
    values = [config.get('python'), os.environ.get('CW3_PYTHON')]
    if os.environ.get('VIRTUAL_ENV'):
        values.append(str(Path(os.environ['VIRTUAL_ENV']) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')))
    values += [str(root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')), sys.executable]
    values += config.get('python_candidates', [])
    values += [shutil.which(name) for name in ('python3.12', 'python3')]
    return list(dict.fromkeys(str(resolve_path(value, root)) for value in values if value))


def discover_python(config, root=ROOT):
    attempts = []
    commands = [[path] for path in python_candidates(config, root) if Path(path).is_file()]
    uv = shutil.which('uv')
    if uv:
        # uv owns a reusable cache outside the checkout. Offline is intentional:
        # unavailable dependencies are a clear blocker, not an implicit download.
        commands.append([uv, 'run', '--offline', '--no-project', '--with-requirements',
                         str(root / 'requirements-build.txt'), 'python'])
    for command in commands:
        extra = {}
        if config.get('pythonpath') and config.get('python') and command[0] == str(resolve_path(config['python'], root)):
            extra['PYTHONPATH'] = os.pathsep.join(str(resolve_path(p, root)) for p in config['pythonpath'])
        try:
            result = subprocess.run(command + ['-c', PROBE], cwd=root, text=True,
                                    capture_output=True, timeout=60, env=dict(os.environ, **extra))
            if result.returncode == 0:
                details = json.loads(result.stdout.strip().splitlines()[-1])
                return dict(command=command, details=details, attempts=attempts, environment=extra)
            attempts.append(dict(command=command, error=result.stderr.strip()[-600:]))
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as error:
            attempts.append(dict(command=command, error=str(error)))
    raise RuntimeError('No usable existing Python environment. Set python in the development config '
                       'or run the source checks in CI. Checked: ' + json.dumps(attempts))


def mono_config(config):
    result = dict(config)
    if config.get('mono_runtime') and config.get('mono_compiler'):
        return result
    for folder in config.get('tool_paths', []):
        folder = resolve_path(folder)
        runtime, compiler = folder / 'mono', folder / 'mcs'
        if runtime.is_file() and compiler.is_file():
            # MonoTools treats configured compiler as a managed exe, not an mcs wrapper.
            executable = folder.parent / 'lib/mono/4.5/mcs.exe'
            if not executable.is_file():continue
            result.update(mono_runtime=str(runtime), mono_compiler=str(executable))
            return result
    return result


def test_source(config, root=ROOT, standalone=True):
    environment = discover_python(config, root)
    command = environment['command']
    process_environment = dict(os.environ, **environment.get('environment', {}))
    for args in (['tools/workflow.py', 'check'], ['-m', 'unittest', 'discover', '-s', 'tests', '-v']):
        subprocess.run(command + args, cwd=root, check=True, timeout=300, env=process_environment)
    result = dict(python=environment['details'], python_checks='passed', standalone_csharp='not_run')
    if standalone:
        import tempfile
        selected = mono_config(config)
        args = ['tools/test.py', '--standalone']
        if selected.get('mono_runtime') and selected.get('mono_compiler'):
            with tempfile.TemporaryDirectory(prefix='cw3-test-config-') as folder:
                path = Path(folder) / 'config.json'
                path.write_text(json.dumps(selected))
                subprocess.run(command + args + ['--config', str(path)], cwd=root, check=True, timeout=300, env=process_environment)
        else:
            subprocess.run(command + args, cwd=root, check=True, timeout=300, env=process_environment)
        result['standalone_csharp'] = 'passed'
    return result
