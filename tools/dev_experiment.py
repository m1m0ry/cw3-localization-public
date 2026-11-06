"""Owned temporary CW3 runtime/profile experiment; never replay a scenario.

Use experiment(...), then recover(directory, backend) after an interruption.
Scenario commands still use NativeMac.exchange with run.record/run.persist.
"""
from contextlib import contextmanager
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid

from dev_lock import desktop_lock
import dev_session as sessions
import mac_runtime_debug as debug


def digest(data):return hashlib.sha256(data).hexdigest()


def profile_basename(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in ('backup', 'journal.json'):
        raise ValueError('Profile name must be a single non-reserved basename')
    return name


# GameSettings.Write serializes MainMenu's unlocks and resolution observations.
# This is opt-in for unlocked campaign experiments, not a general settings merge.
CAMPAIGN_UNLOCKS = {'unlockProspector', 'unlockTormented', 'unlockAlpha', 'unlockCredits',
                    'unlockProjects', 'unlockColonialSpace', 'unlockDMD', 'unlockLoadFile'}


def prepared_settings(original, profile):
    text = original.decode('utf-8-sig')
    for tag, value in (('CustomDataPath', escape(str(profile))), ('UseCustomDataPath', 'True')):
        text, count = re.subn('<' + tag + '>[^<]*</' + tag + '>', lambda _: '<' + tag + '>' + value + '</' + tag + '>', text)
        if count != 1:raise RuntimeError('Expected one GameSettings ' + tag)
    return text.encode()


def campaign_settings_match(prepared, current):
    def fields(data):
        # The original game's StringWriter declares utf-16 but WriteAllText
        # writes UTF-8. Decode actual bytes before parsing the declaration.
        root = ElementTree.fromstring(data.decode('utf-8-sig'))
        if root.tag != 'GameSettings' or root.attrib or (root.text or '').strip():raise ValueError('Settings root differs')
        result = {}
        for child in root:
            if child.tag in result or child.attrib or len(child) or (child.tail or '').strip():raise ValueError('Settings structure differs')
            result[child.tag] = child.text or ''
        return result
    try:
        before, after = fields(prepared), fields(current)
        if before.keys() != after.keys():return False
        for name, value in after.items():
            if value == before[name]:continue
            if name in CAMPAIGN_UNLOCKS and before[name] == 'False' and value == 'True':continue
            if name in ('WindowWidth', 'WindowHeight') and all(re.fullmatch(r'[1-9][0-9]*', v) and int(v) <= 2147483647 for v in (before[name], value)):continue
            return False
        return True
    except (ValueError, UnicodeError, ElementTree.ParseError):return False


def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('Linked experiment path: ' + str(path))
    if path.exists() and not path.is_file():raise RuntimeError('Not a regular file: ' + str(path))
    return path.read_bytes() if path.exists() else None


def durable_write(path, data, mode=0o600, exclusive=False):
    """Publish whole bytes only. Never expose a partly written runtime/marker."""
    fd, name = tempfile.mkstemp(prefix='.experiment-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data);stream.flush();os.fchmod(stream.fileno(), mode);os.fsync(stream.fileno())
        if exclusive:os.link(temporary, path)
        else:os.replace(temporary, path)
        sync_directory(path.parent)
    finally:temporary.unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


class Experiment:
    def __init__(self, directory, backend, claim):
        self.directory = directory
        self.path = directory / 'journal.json'
        self.backend = backend
        self.claim = claim
        self.record = None
        self.profile_name = 'profile'

    @property
    def profile(self):return self.directory / profile_basename(self.record['profile_name'] if self.record else self.profile_name)

    def persist(self):
        if self.directory.is_symlink() or self.directory.stat().st_ino != self.record['directory_inode']:
            raise RuntimeError('Experiment directory ownership changed: ' + str(self.directory))
        regular(self.path)
        durable_write(self.path, (json.dumps(self.record, ensure_ascii=False, indent=2) + '\n').encode())

    def processes(self):
        try:
            rows = self.backend.processes()
            if not isinstance(rows, list):raise RuntimeError('Process observation returned no PID list')
            return rows
        except Exception as error:raise RuntimeError('Process state unknown; recovery retained: ' + str(error)) from error

    def no_request(self):
        request = Path(self.record['state']) / 'cw3-debug/request.txt'
        pending = self.record.get('request')
        if pending and not request.exists() and not request.is_symlink():
            # A crash can leave the journal pending after the existing endpoint
            # published its terminal response. Observe that ID; never resend it.
            raw = regular(request.with_name('response.json'))
            try:response = json.loads(raw) if raw else {}
            except (ValueError, UnicodeError):response = {}
            if not isinstance(response, dict):response = {}
            result = response.get('result')
            queued = isinstance(result, dict) and result.get('queued')
            # Quit's response acknowledges dispatch, not process exit. The stop
            # callback observes exit without issuing Quit a second time.
            if pending['command'] == 'quit' and response.get('ok') is True:queued = False
            if queued and pending['command'] == 'screenshot' and result.get('path'):
                capture = Path(result['path'])
                if capture.parent.resolve() == request.parent.resolve() and sessions.complete_capture(capture):queued = False
            if response.get('id') == pending['id'] and type(response.get('ok')) is bool and not queued:
                if response['ok']:self.record['evidence'][pending['command']] = response
                else:self.record.setdefault('failed_requests', []).append(dict(request=pending, response=response))
                self.record.pop('request');self.persist();pending = None
        if pending or request.exists() or request.is_symlink():
            raise RuntimeError('Pending diagnostics request; reconcile the same ID before recovery: ' +
                               (str(pending) if pending else str(request)))

    def idle(self):
        self.no_request()
        if self.processes():raise RuntimeError('Game is active; no experiment files were restored')
        if self.record.get('launch') == 'pending':
            raise RuntimeError('Launch outcome unknown; inspect Steam/process state before recovery; do not relaunch')

    def begin(self, settings, runtime, verify_required=False, profile_name='profile', campaign_settings=False):
        self.profile_name = profile_basename(profile_name)
        # All inputs are read before claiming or altering the installation.
        if self.directory.exists():raise RuntimeError('Experiment directory already exists; recover it or use a fresh directory: ' + str(self.directory))
        if self.processes():raise RuntimeError('Existing game is active; no experiment was prepared')
        folder = debug.diagnostics_folder(self.backend.state)
        if any((folder / name).exists() or (folder / name).is_symlink() for name in ('enabled.txt', 'request.txt')):
            raise RuntimeError('Existing diagnostics marker/request; reconcile it before the experiment')
        targets = [settings, self.backend.game / sessions.RUNTIME, self.backend.game / sessions.REGISTRY, folder / 'enabled.txt']
        before = [regular(p) for p in targets]
        if any(data is None for data in before[:3]):raise RuntimeError('Settings/runtime/fonts input is missing')
        candidate = regular(runtime)
        if candidate is None:raise RuntimeError('Experiment runtime is missing')
        fonts = json.loads(before[2])
        if fonts.get('runtime_sha256') != digest(before[1]):raise RuntimeError('Installed runtime/fonts pair differs')
        fonts['runtime_sha256'] = digest(candidate)
        after = [prepared_settings(before[0], self.profile), candidate,
                 (json.dumps(fonts, ensure_ascii=False, indent=2) + '\n').encode(), (digest(candidate) + '\n').encode()]
        self.directory.mkdir(mode=0o700);sync_directory(self.directory.parent)
        self.record = dict(format=1, id=uuid.uuid4().hex, phase='preparing', game=str(self.backend.game),
                           state=str(self.backend.state), directory_inode=self.directory.stat().st_ino,
                           files=[], directories={'backup': None, self.profile_name: None}, profile_name=self.profile_name,
                           verify_required=verify_required, campaign_settings=campaign_settings, evidence={})
        for number, (target, original, replacement) in enumerate(zip(targets, before, after)):
            self.record['files'].append(dict(path=str(target), before=digest(original) if original is not None else None,
                                            after=digest(replacement), backup=str(number), mode=target.stat().st_mode & 0o777 if original is not None else 0o600))
        self.persist()
        durable_write(self.claim, (json.dumps(dict(journal=str(self.path), id=self.record['id'])) + '\n').encode(), exclusive=True)
        backups = self.directory / 'backup';backups.mkdir()
        self.record['directories']['backup'] = backups.stat().st_ino;self.persist()
        for row, original in zip(self.record['files'], before):
            if original is not None:durable_write(backups / row['backup'], original)
        # Journal, ownership and every original are durable before the first
        # live mutation, including the profile and diagnostics opt-in.
        self.profile.mkdir()
        self.record['directories'][self.profile_name] = self.profile.stat().st_ino;self.persist()
        (self.profile / 'creeperworld3/data').mkdir(parents=True)
        for row, replacement in zip(self.record['files'], after):
            self.idle()
            target = Path(row['path'])
            current = regular(target)
            if (digest(current) if current is not None else None) != row['before']:
                raise RuntimeError('File changed before preparation: ' + str(target))
            if row['before'] is None:
                debug.context(self.backend.game, self.backend.state)
                target.parent.mkdir(exist_ok=True)
            self.record['step'] = 'prepare ' + str(target);self.persist()
            durable_write(target, replacement, row['mode'], exclusive=row['before'] is None)
        self.record['phase'] = 'ready';self.record.pop('step', None);self.persist()

    def launch(self):
        """The controller keeps its existing Steam conflict/wait gate."""
        self.idle()
        if self.record.get('launch'):raise RuntimeError('Launch already attempted; observe it, do not repeat it')
        self.record['launch'] = 'pending';self.persist()
        self.backend.launch()

    def started(self):
        if self.record.get('launch') != 'pending':raise RuntimeError('No pending launch to observe')
        pids = self.processes()
        if not pids:raise RuntimeError('Launch outcome unknown; no game process observed')
        self.record['pids'] = pids;self.record['launch'] = 'observed';self.persist()

    def owned_current(self, row, current):
        if current is None:return False
        if digest(current) == row['after']:return True
        if row['backup'] == '0' and self.record.get('campaign_settings'):
            original = regular(self.directory / 'backup' / row['backup'])
            if original is not None and digest(original) == row['before']:
                prepared = prepared_settings(original, self.profile)
                return digest(prepared) == row['after'] and campaign_settings_match(prepared, current)
        return False

    def restore(self, stop=None, verify=None):
        if self.record['phase'] == 'complete':return self.record
        if self.claim.exists():
            claim = json.loads(regular(self.claim))
            if claim != dict(journal=str(self.path), id=self.record['id']):raise RuntimeError('Experiment claim changed; recovery retained')
        if self.directory.is_symlink() or self.directory.stat().st_ino != self.record['directory_inode']:
            raise RuntimeError('Experiment directory ownership changed: ' + str(self.directory))
        self.no_request()
        pids = self.processes()
        if pids:
            if self.record.get('launch') == 'pending':self.started()
            if pids != self.record.get('pids'):raise RuntimeError('Game process ownership changed; recovery retained')
            if stop is None:raise RuntimeError('Game is active; normal scenario exit is required before recovery')
            stop(self)
        self.idle()
        self.record['phase'] = 'restoring';self.persist()
        # Preflight every target before restoring any: never overwrite unrelated
        # edits, even if only one of the four preparation writes completed.
        for row in self.record['files']:
            current = regular(Path(row['path']))
            current_hash = digest(current) if current is not None else None
            if current_hash != row['before'] and not self.owned_current(row, current):
                raise RuntimeError('Unrelated modification; recovery retained: ' + row['path'])
            if current_hash != row['before'] and row['before'] is not None:
                backup = regular(self.directory / 'backup' / row['backup'])
                if backup is None or digest(backup) != row['before']:raise RuntimeError('Recovery backup changed: ' + row['path'])
        for row in reversed(self.record['files']):
            self.idle()
            target = Path(row['path']);current = regular(target)
            current_hash = digest(current) if current is not None else None
            if current_hash == row['before']:continue
            if not self.owned_current(row, current):raise RuntimeError('File changed during recovery: ' + str(target))
            self.record['step'] = 'restore ' + str(target);self.persist()
            if row['before'] is None:target.unlink();sync_directory(target.parent)
            else:
                backup = regular(self.directory / 'backup' / row['backup'])
                if backup is None or digest(backup) != row['before']:raise RuntimeError('Recovery backup changed: ' + str(target))
                durable_write(target, backup, row['mode'])
        self.idle()
        for row in self.record['files']:
            value = regular(Path(row['path']))
            if (digest(value) if value is not None else None) != row['before']:raise RuntimeError('Restoration verification failed: ' + row['path'])
        if self.record.get('verify_required') and verify is None:
            raise RuntimeError('Scenario verification callback is required before experiment cleanup')
        if verify:verify()
        self.record['phase'] = 'restored';self.persist()
        # Keep originals/profile until all restores and caller checks succeeded.
        for folder in (self.profile, self.directory / 'backup'):
            if folder.is_symlink():raise RuntimeError('Owned cleanup directory was replaced: ' + str(folder))
            if folder.exists():
                expected = self.record['directories'][folder.name]
                if expected is None and folder.is_dir() and not any(folder.iterdir()):
                    # Durable mkdir intent, then crash before inode publication.
                    # No contents are written before that publication; remove
                    # only the empty planned directory, never adopt its contents.
                    folder.rmdir()
                elif folder.stat().st_ino == expected:shutil.rmtree(folder)
                else:raise RuntimeError('Owned cleanup directory changed: ' + str(folder))
        if self.claim.exists():
            claim = json.loads(regular(self.claim))
            if claim != dict(journal=str(self.path), id=self.record['id']):raise RuntimeError('Experiment claim changed; not removed')
            self.claim.unlink();sync_directory(self.claim.parent)
        self.record['phase'] = 'complete';self.record.pop('step', None);self.record.pop('blocked', None);self.persist()
        return self.record

    def recover(self, stop=None, verify=None):
        try:return self.restore(stop, verify)
        except BaseException as error:
            self.record['blocked'] = str(error)
            self.persist()
            raise


@contextmanager
def experiment(directory, backend, *, settings, runtime, stop=None, verify=None, profile_name='profile', campaign_settings=False):
    directory = Path(directory).absolute()
    with desktop_lock(directory / 'journal.json') as claim:
        run = Experiment(directory, backend, claim)
        try:
            run.begin(Path(settings).absolute(), Path(runtime).absolute(), verify_required=verify is not None, profile_name=profile_name, campaign_settings=campaign_settings)
            yield run
        finally:
            # This covers failures inside begin(), not only after yield.
            if run.record is not None:run.recover(stop, verify)


def recover(directory, backend, *, stop=None, verify=None):
    """Restore the same journal only. Never prepare, launch, or reissue commands."""
    directory = Path(directory).absolute()
    with desktop_lock(directory / 'journal.json') as claim:
        run = Experiment(directory, backend, claim)
        run.record = json.loads(regular(run.path))
        if (str(backend.game), str(backend.state)) != (run.record['game'], run.record['state']):
            raise RuntimeError('Recovery backend does not match the recorded game/state')
        return run.recover(stop, verify)
