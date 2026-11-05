"""Resumable native Mac install/start/smoke checks, using existing project interfaces."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import subprocess
import tempfile
import time
import uuid

import game_target
import mac_runtime_debug as debug
import player_install as player

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = 'CW3Localization/Runtime/CW3ExternalRuntime.dll'
REGISTRY = 'CW3Localization/fonts.json'


def complete_capture(path):
    if not path.is_file() or path.stat().st_size < 20:return False
    with path.open('rb') as stream:
        if stream.read(8) != b'\x89PNG\r\n\x1a\n':return False
        stream.seek(-12, 2)
        return stream.read() == b'\x00\x00\x00\x00IEND\xaeB`\x82'


def retry_probe(record):
    pending = record.get('request')
    if not pending:
        capture = record.get('evidence', {}).get('screenshot', {}).get('result')
        if capture and not complete_capture(Path(capture['path'])):
            request = Path(record['state']) / 'cw3-debug/request.txt'
            if request.exists() or request.is_symlink():
                raise RuntimeError('A different request is pending; it was not cancelled')
            # A queued response ends the request, not the asynchronous PNG write.
            # Retry only that incomplete capture; keep installation and other probes.
            record['evidence'].pop('screenshot')
        return
    if pending['command'] not in ('runtime_probe', 'display_probe', 'screenshot'):
        raise ValueError('Only fixed read-only smoke probes may be retried')
    request = Path(record['state']) / 'cw3-debug/request.txt'
    if request.exists():
        if request.is_symlink() or request.read_text().split('\t', 1)[0] != pending['id']:
            raise RuntimeError('A different request is pending; it was not cancelled')
        request.unlink()
    record.setdefault('abandoned_requests', []).append(pending)
    record.pop('request')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def package_identity(package):
    manifest = player.read(package / 'manifest.json')
    if manifest.get('kind') == 'rendering_component':
        raise ValueError('Legacy rendering components cannot replace the stable bridge; use a complete package')
    player.validate_manifest(manifest)
    for row in manifest['files']:
        source = player.safe(package, row['file'])
        if player.digest(source) != row['after'] or source.stat().st_size != row['bytes']:
            raise ValueError('Candidate payload changed: ' + row['file'])
    if manifest['target_id'] == game_target.MACOS:
        registry = player.read(player.safe(package, REGISTRY))
        if registry.get('runtime_sha256') != player.digest(player.safe(package, RUNTIME)):
            raise ValueError('External runtime and fonts.json must come from the same build')
    return manifest, player.digest(package / 'manifest.json')


def installed_hashes(game, manifest):
    return {row['file']: player.digest(player.installed_path(game, row['file'], manifest))
            for row in manifest['files']}


def wanted_hashes(manifest):
    return {row['file']: row['after'] for row in manifest['files']}


def process_rows(game):
    """A real process query, not AppleScript's sandbox-dependent `is running`."""
    exe = str(game / 'CW3.app/Contents/MacOS/CW3')
    result = subprocess.run(['/bin/ps', '-axo', 'pid=,command='], capture_output=True,
                            text=True, check=True, timeout=10)
    if not result.stdout.strip():raise RuntimeError('Process observation returned no data')
    rows = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and (fields[1] == exe or fields[1].startswith(exe + ' ')):
            rows.append(int(fields[0]))
    return rows


def wait_until(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:return value
        if time.monotonic() >= deadline:raise TimeoutError(message)
        time.sleep(.25)


@contextmanager
def awake():
    process = subprocess.Popen(['/usr/bin/caffeinate', '-di', '-w', str(os.getpid())])
    try:yield
    finally:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait()


class NativeMac:
    def __init__(self, config):
        self.previous_runtime = config.get('previous_runtime_sha256')
        self.game = Path(config['game']).expanduser().resolve()
        self.state = Path(config['state']).expanduser().resolve()
        self.steam = Path(config.get('steam', '/Applications/Steam.app/Contents/MacOS/steam_osx')).expanduser()

    def processes(self):return process_rows(self.game)

    def quit(self, timeout):
        if not self.processes():return
        # Normal Quit AppleEvent. Do not turn an unresponsive app into an automatic KILL.
        subprocess.run(['/usr/bin/osascript', '-e',
                        'on run argv\ntell application (item 1 of argv) to quit\nend run',
                        str(self.game / 'CW3.app')], check=True, timeout=timeout,
                       capture_output=True, text=True)
        wait_until(lambda: not self.processes(), timeout, 'Normal Quit did not finish; game is unchanged')

    def install(self, package, manifest):
        player.install(self.game, manifest, package)

    def enable(self):
        _, folder, expected = debug.context(self.game, self.state)
        marker = folder / 'enabled.txt'
        request = folder / 'request.txt'
        if request.exists() or request.is_symlink():
            raise RuntimeError('An earlier diagnostics request is outstanding; inspect it before continuing')
        if marker.is_file() and not marker.is_symlink() and marker.read_text().strip() == expected:return
        if marker.exists() or marker.is_symlink():
            if marker.is_symlink() or not marker.is_file() or marker.read_text().strip() != self.previous_runtime:
                raise RuntimeError('Diagnostics marker belongs to an unrelated runtime; inspect it before continuing')
            # The session captured this runtime before installation. Refresh its
            # old opt-in only after the game has stopped, not an unrelated marker.
            debug.action(self.game, self.state, ['disable'], ROOT / 'local-only/evidence')
        debug.action(self.game, self.state, ['enable'], ROOT / 'local-only/evidence')

    def launch(self):
        if not self.steam.is_file():raise RuntimeError('Configured Steam executable is unavailable')
        subprocess.run([str(self.steam), '-applaunch', '280220'], capture_output=True,
                       text=True, check=True, timeout=15)

    def exchange(self, record, command, persist, timeout):
        _, folder, expected = debug.context(self.game, self.state)
        marker = folder / 'enabled.txt'
        if not marker.is_file() or marker.is_symlink() or marker.read_text().strip() != expected:
            raise RuntimeError('Diagnostics are not enabled for the installed runtime')
        request, response = folder / 'request.txt', folder / 'response.json'
        pending = record.get('request')
        if pending:
            if pending['command'] != command:raise RuntimeError('Finish the current diagnostics request first')
            ident = pending['id']
        else:
            if request.exists() or request.is_symlink():
                raise RuntimeError('Another diagnostics request is pending; inspect it before continuing')
            ident = uuid.uuid4().hex
            record['request'] = {'id': ident, 'command': command, 'submitted': False}
            persist()
        pending = record['request']
        if not pending['submitted']:
            row = ident + '\t' + command + '\n'
            # Exclusive creation: never overwrite somebody else's queued command.
            if request.exists():
                if request.is_symlink() or request.read_text() != row:
                    raise RuntimeError('A different diagnostics request is pending')
            else:
                # Persist before dispatch, so interruption cannot cause blind resubmission.
                pending['submitted'] = True;persist()
                fd, name = tempfile.mkstemp(prefix='.dev-request-', dir=folder)
                temporary = Path(name)
                try:
                    with os.fdopen(fd, 'w') as stream:
                        stream.write(row);stream.flush();os.fsync(stream.fileno())
                    # Atomic and exclusive publication. The game never observes
                    # an empty/partial request, and an existing request is not replaced.
                    os.link(temporary, request)
                except OSError:
                    pending['submitted'] = False;persist()
                    raise
                finally:temporary.unlink(missing_ok=True)
            pending['submitted'] = True;persist()
        def received():
            if not response.exists():return None
            if response.is_symlink():raise RuntimeError('Diagnostics response is linked')
            try:result = json.loads(response.read_text())
            except json.JSONDecodeError:return None
            return result if result.get('id') == ident else None
        result = wait_until(received, timeout,
                            'Runtime has not answered. Request retained; resume waits for this ID. If delivery was interrupted, use resume --retry-probe. '
                            'Check the visible system prompt or current launch log; timeout alone does not prove a permission issue.')
        if not result.get('ok'):raise RuntimeError('Runtime refused: ' + str(result.get('error')))
        record['evidence'][command] = result
        record.pop('request', None);persist()
        if command == 'screenshot':
            path = Path(result['result']['path'])
            if path.parent.resolve() != folder.resolve():raise ValueError('Capture path is outside diagnostics')
            wait_until(lambda: complete_capture(path), timeout,
                       'Screenshot queued but not written yet; resume checks the same file, or resume --retry-probe requests a new capture')
        return result['result']


def new_session(config, package):
    manifest, digest = package_identity(package)
    if manifest['target_id'] != game_target.MACOS:raise ValueError('Automated desktop apply currently targets native macOS')
    return dict(format=1, id=uuid.uuid4().hex, phase='prepared', created=time.time(),
                game=str(Path(config['game']).expanduser().resolve()),
                state=str(Path(config['state']).expanduser().resolve()),
                steam=config.get('steam', '/Applications/Steam.app/Contents/MacOS/steam_osx'),
                package=str(package.resolve()), package_sha256=digest,
                previous_runtime_sha256=player.digest(Path(config['game']).expanduser().resolve() / RUNTIME),
                evidence={}, history=[])


def advance(record, persist, backend, timeout=20):
    """Persist each boundary. Interrupted install is idempotent; launch is never blindly repeated."""
    package = Path(record['package'])
    manifest, digest = package_identity(package)
    if digest != record['package_sha256']:raise ValueError('Candidate changed; start a new session explicitly')
    def phase(value):
        record['phase'] = value;record['history'].append({'phase': value, 'time': time.time()});persist()
    if record['phase'] == 'prepared':
        backend.quit(timeout);phase('installing')
    if record['phase'] == 'installing':
        backend.install(package, manifest)
        actual = installed_hashes(backend.game, manifest)
        if actual != wanted_hashes(manifest):raise ValueError('Installed bytes differ from candidate')
        record['installed'] = actual
        backend.enable();phase('installed')
    if record['phase'] == 'installed':
        if backend.processes():raise RuntimeError('A process started before this session; quit it before starting this candidate')
        record['launch_time'] = time.time();phase('starting')
        backend.launch();phase('waiting_runtime')
    if record['phase'] == 'starting':
        # The launch call was interrupted. Query, do not launch a second copy.
        if not backend.processes():raise RuntimeError('Launch outcome unknown. No process observed; inspect Steam before retrying a new launch')
        phase('waiting_runtime')
    if record['phase'] in ('waiting_runtime', 'checking', 'verified'):
        if installed_hashes(backend.game, manifest) != record['installed']:
            raise RuntimeError('Installed candidate changed since this session')
        if record['phase'] == 'verified':return record
        processes = wait_until(backend.processes, timeout, 'Steam has not produced a game process. Candidate remains installed; inspect this launch before retrying')
        if record.get('pids') and record['pids'] != processes:
            raise RuntimeError('Game process changed; previous diagnostics do not verify this launch')
        record['pids'] = processes;persist()
        runtime = record['evidence'].get('runtime_probe', {}).get('result')
        if not runtime:
            runtime = backend.exchange(record, 'runtime_probe', persist, timeout)
        if runtime.get('scene') != 'MainMenu':
            record['evidence'].pop('runtime_probe', None);persist()
            raise RuntimeError('Runtime responds in ' + str(runtime.get('scene')) + '; reach MainMenu then resume')
        if runtime.get('rendering_abi') != 'v1' or runtime.get('renderer_assembly') != 'CW3ExternalRuntime' or runtime.get('rendering_bound') is not True:
            record['evidence'].pop('runtime_probe', None);persist()
            raise RuntimeError('Runtime did not confirm the external rendering bridge; use a matching complete candidate')
        phase('checking')
        for command in ('display_probe', 'screenshot'):
            if command not in record['evidence']:
                backend.exchange(record, command, persist, timeout)
        display = record['evidence']['display_probe']['result']
        if display.get('scene') != 'MainMenu' or not display.get('controls'):
            record['evidence'].pop('display_probe', None)
            record['evidence'].pop('screenshot', None);persist()
            raise RuntimeError('Display probe did not observe MainMenu text controls; resume after returning to the menu')
        capture = record['evidence']['screenshot']['result']
        wait_until(lambda: complete_capture(Path(capture['path'])),
                   timeout, 'Screenshot is still queued; resume checks the same file, or resume --retry-probe requests a new capture')
        phase('verified')
    return record
