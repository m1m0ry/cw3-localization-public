"""Experiment rollback fault tests: temporary bytes and a fake process boundary."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dev
import dev_experiment as experiment
import dev_lock
import dev_session as sessions


class FakeDesktop:
    def __init__(self, root):
        self.game = root / 'game';self.state = root / 'CW3Localization'
        self.running = [];self.launches = 0
    def processes(self):return self.running
    def launch(self):self.launches += 1;self.running = [42]


@unittest.skipUnless(os.name == 'posix', 'Native Mac experiments require POSIX flock and fork')
class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve();self.backend = FakeDesktop(self.root)
        self.patch_lock = patch.object(dev_lock, 'ROOT', self.root);self.patch_lock.start();self.addCleanup(self.patch_lock.stop)
        self.directory = self.root / 'experiment';self.settings = self.root / 'GameSettings.xml';self.candidate = self.root / 'candidate.dll'
        self.runtime = self.backend.game / sessions.RUNTIME;self.fonts = self.backend.game / sessions.REGISTRY
        self.debug = self.backend.state / 'cw3-debug';self.debug.mkdir(parents=True)
        (self.backend.state / 'font-status.json').write_text('{}')
        self.runtime.parent.mkdir(parents=True)
        self.original = {self.settings: b'\xef\xbb\xbf<settings>\r\n<CustomDataPath>user</CustomDataPath><UseCustomDataPath>False</UseCustomDataPath>\r\n</settings>',
                         self.runtime: b'formal\x00runtime',
                         self.fonts: json.dumps({'runtime_sha256': experiment.digest(b'formal\x00runtime'), 'user-font': 'keep'}).encode()}
        for path, data in self.original.items():path.write_bytes(data)
        self.candidate.write_bytes(b'probe runtime');self.claim = self.root / 'local-only/evidence/dev-install.experiment.json'

    def context(self, **kwargs):
        return experiment.experiment(self.directory, self.backend, settings=self.settings, runtime=self.candidate, **kwargs)

    def read(self):return json.loads((self.directory / 'journal.json').read_text())

    def assert_restored(self):
        for path, data in self.original.items():self.assertEqual(path.read_bytes(), data)
        self.assertFalse((self.debug / 'enabled.txt').exists())
        self.assertFalse((self.directory / 'backup').exists());self.assertFalse((self.directory / 'profile').exists())
        self.assertFalse(self.claim.exists());self.assertEqual(self.read()['phase'], 'complete')

    def test_failure_before_and_after_each_prepare_write_restores_original_bytes(self):
        for target in (self.settings, self.runtime, self.fonts, self.debug / 'enabled.txt'):
            for after in (False, True):
                with self.subTest(target=target.name, after=after):
                    self.directory = self.root / ('experiment-' + target.name + str(after))
                    original_write = experiment.durable_write;fired = False
                    def fail(path, data, *args, **kwargs):
                        nonlocal fired
                        if path == target and not fired:
                            fired = True
                            # Claim + complete original backups precede every live write.
                            self.assertTrue(self.claim.exists())
                            self.assertEqual(len(list((self.directory / 'backup').iterdir())), 3)
                            if after:original_write(path, data, *args, **kwargs)
                            raise OSError('prepare failure')
                        return original_write(path, data, *args, **kwargs)
                    with patch.object(experiment, 'durable_write', side_effect=fail):
                        with self.assertRaisesRegex(OSError, 'prepare failure'):
                            with self.context():self.fail('failed prepare must never yield')
                    self.assertTrue(fired);self.assert_restored()

    def test_backup_failure_before_first_mutation_is_also_recovered(self):
        original_write = experiment.durable_write
        def fail(path, *args, **kwargs):
            if path.parent.name == 'backup':raise OSError('backup unavailable')
            return original_write(path, *args, **kwargs)
        with patch.object(experiment, 'durable_write', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'backup unavailable'):
                with self.context():self.fail('must not yield')
        self.assert_restored()

    def test_success_and_duplicate_live_lock_and_persistent_ownership(self):
        with self.context() as run:
            self.assertNotEqual(self.settings.read_bytes(), self.original[self.settings])
            self.assertTrue(run.profile.is_dir())
            with self.assertRaisesRegex(RuntimeError, 'Another maintenance'):
                with dev.desktop_lock():pass
            with self.assertRaisesRegex(RuntimeError, 'Another maintenance'):
                with self.context():pass
        self.assert_restored()
        self.assertEqual(experiment.recover(self.directory, self.backend)['phase'], 'complete')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            with self.context():pass

    def test_restore_failure_can_be_recovered_twice_without_premature_cleanup(self):
        original_write = experiment.durable_write;fired = False
        def fail(path, data, *args, **kwargs):
            nonlocal fired
            if path == self.runtime and data == self.original[self.runtime] and not fired:
                fired = True;original_write(path, data, *args, **kwargs);raise OSError('restore interrupted after write')
            return original_write(path, data, *args, **kwargs)
        with patch.object(experiment, 'durable_write', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'restore interrupted'):
                with self.context():pass
        self.assertNotEqual(self.read()['phase'], 'complete');self.assertTrue((self.directory / 'backup').exists())
        self.assertTrue((self.directory / 'profile').exists())
        with self.assertRaisesRegex(RuntimeError, 'unfinished experiment'):
            with dev.desktop_lock():pass
        with self.assertRaisesRegex(RuntimeError, 'unfinished experiment'):
            with experiment.experiment(self.root / 'other', self.backend, settings=self.settings, runtime=self.candidate):pass
        experiment.recover(self.directory, self.backend);experiment.recover(self.directory, self.backend)
        self.assert_restored()

    def test_unrelated_file_or_backup_changes_block_without_overwriting(self):
        for corrupt_backup in (False, True):
            with self.subTest(backup=corrupt_backup):
                self.directory = self.root / ('changes-' + str(corrupt_backup))
                with self.assertRaisesRegex(RuntimeError, 'changed|Unrelated'):
                    with self.context():
                        path = self.directory / 'backup/1' if corrupt_backup else self.fonts
                        previous = path.read_bytes();path.write_bytes(b'unrelated edit')
                        prepared = {p: p.read_bytes() for p in self.original}
                self.assertEqual(path.read_bytes(), b'unrelated edit')
                self.assertEqual({p: p.read_bytes() for p in self.original}, prepared)
                self.assertNotEqual(self.read()['phase'], 'complete');self.assertTrue(self.claim.exists())
                path.write_bytes(previous);experiment.recover(self.directory, self.backend);self.assert_restored()

    def test_unknown_process_and_pending_request_never_stop_restore_or_reissue(self):
        for state in ('unknown-process', 'pending-record', 'pending-file', 'unknown-launch', 'different-process'):
            with self.subTest(state=state):
                self.directory = self.root / state;stop_calls = []
                with self.assertRaisesRegex(RuntimeError, 'unknown|Pending|ownership changed'):
                    with self.context(stop=lambda run: stop_calls.append(True)) as run:
                        if state == 'unknown-process':self.backend.running = None
                        elif state == 'pending-record':run.record['request'] = {'id': 'same-id', 'command': 'campaign_launch', 'submitted': True};run.persist()
                        elif state == 'pending-file':(self.debug / 'request.txt').write_text('other-id\tquit\n')
                        elif state == 'unknown-launch':
                            run.launch();self.backend.running = []
                        else:
                            run.launch();run.started();self.backend.running = [99]
                        prepared = {p: p.read_bytes() for p in self.original}
                self.assertEqual(stop_calls, []);self.assertEqual({p: p.read_bytes() for p in self.original}, prepared)
                self.assertNotEqual(self.read()['phase'], 'complete');self.assertTrue((self.directory / 'backup').exists())
                # Simulate explicit reconciliation of the same request/launch,
                # rather than asking the helper to discard an unknown outcome.
                self.backend.running = [];(self.debug / 'request.txt').unlink(missing_ok=True)
                record = self.read();record.pop('request', None);record['launch'] = 'observed'
                (self.directory / 'journal.json').write_text(json.dumps(record))
                experiment.recover(self.directory, self.backend);self.assert_restored()

    def test_normal_exit_callback_and_verification_must_finish_before_cleanup(self):
        def stop(run):self.backend.running = []
        def verify():raise RuntimeError('app verification failed')
        with self.assertRaisesRegex(RuntimeError, 'app verification'):
            with self.context(stop=stop, verify=verify) as run:
                run.launch();run.started()
        for path, data in self.original.items():self.assertEqual(path.read_bytes(), data)
        self.assertTrue((self.directory / 'profile').exists());self.assertTrue((self.directory / 'backup').exists())
        with self.assertRaisesRegex(RuntimeError, 'app verification'):
            experiment.recover(self.directory, self.backend, verify=verify)
        with self.assertRaisesRegex(RuntimeError, 'callback is required'):
            experiment.recover(self.directory, self.backend)
        experiment.recover(self.directory, self.backend, verify=lambda: None);self.assert_restored()

    def test_matching_terminal_response_recovers_without_reissuing_request(self):
        for ok in (True, False):
            with self.subTest(ok=ok):
                self.directory = self.root / ('response-' + str(ok))
                with self.assertRaisesRegex(RuntimeError, 'Pending'):
                    with self.context() as run:
                        run.record['request'] = {'id': 'same-id', 'command': 'campaign_pause', 'submitted': True};run.persist()
                response = {'id': 'same-id', 'ok': ok, 'result': {'paused': True}, 'error': 'refused'}
                (self.debug / 'response.json').write_text(json.dumps(response))
                record = experiment.recover(self.directory, self.backend)
                self.assertNotIn('request', record);self.assertEqual(self.backend.launches, 0)
                if ok:self.assertEqual(record['evidence']['campaign_pause'], response)
                else:self.assertEqual(record['failed_requests'][0]['response'], response)
                self.assert_restored();(self.debug / 'response.json').unlink()

    def test_unmatched_or_queued_response_cannot_clear_pending_request(self):
        with self.assertRaisesRegex(RuntimeError, 'Pending'):
            with self.context() as run:
                run.record['request'] = {'id': 'same-id', 'command': 'screenshot', 'submitted': True};run.persist()
        for response in ({'id': 'other-id', 'ok': True}, {'id': 'same-id'},
                         {'id': 'same-id', 'ok': True, 'result': {'queued': True}}):
            with self.subTest(response=response):
                (self.debug / 'response.json').write_text(json.dumps(response))
                with self.assertRaisesRegex(RuntimeError, 'Pending'):experiment.recover(self.directory, self.backend)
                self.assertEqual(self.read()['request']['id'], 'same-id');self.assertTrue(self.claim.exists())

    def test_queued_quit_waits_for_exit_without_reissuing_and_then_recovers(self):
        def waiting(run):
            self.assertTrue(run.record['evidence']['quit']['result']['queued'])
            self.assertNotIn('request', run.record)
            raise TimeoutError('normal quit still pending')
        with self.assertRaisesRegex(TimeoutError, 'quit still pending'):
            with self.context(stop=waiting) as run:
                run.launch();run.started()
                run.record['request'] = {'id': 'quit-id', 'command': 'quit', 'submitted': True};run.persist()
                (self.debug / 'response.json').write_text(json.dumps({'id': 'quit-id', 'ok': True, 'result': {'queued': True}}))
        self.assertEqual(self.runtime.read_bytes(), self.candidate.read_bytes());self.assertTrue(self.claim.exists())
        with self.assertRaisesRegex(TimeoutError, 'quit still pending'):
            experiment.recover(self.directory, self.backend, stop=waiting)
        self.backend.running = []
        experiment.recover(self.directory, self.backend);self.assertEqual(self.backend.launches, 1);self.assert_restored()

    def campaign_fixture(self):
        data = ('<?xml version="1.0" encoding="utf-16"?>\n<GameSettings>\n'
                '  <CustomDataPath>user</CustomDataPath><UseCustomDataPath>False</UseCustomDataPath>\n'
                '  <WindowWidth>1280</WindowWidth><WindowHeight>720</WindowHeight><SoundVolume>0.5</SoundVolume>\n' +
                ''.join('  <' + tag + '>False</' + tag + '>\n' for tag in sorted(experiment.CAMPAIGN_UNLOCKS)) + '</GameSettings>').encode()
        self.settings.write_bytes(data);self.original[self.settings] = data

    def test_campaign_setting_changes_are_opt_in_and_survive_recovery_reload(self):
        self.campaign_fixture()
        for allowed in (False, True):
            with self.subTest(allowed=allowed):
                self.directory = self.root / ('campaign-' + str(allowed))
                with self.assertRaisesRegex(RuntimeError, 'Pending'):
                    with self.context(campaign_settings=allowed) as run:
                        prepared = self.settings.read_bytes()
                        text = prepared.decode().replace('>False<', '>True<').replace('>1280<', '>1920<').replace('>720<', '>1080<')
                        self.settings.write_bytes(text.replace('  ', '').encode())
                        run.record['request'] = {'id': 'same-id', 'command': 'campaign_pause', 'submitted': True};run.persist()
                (self.debug / 'response.json').write_text(json.dumps({'id': 'same-id', 'ok': True, 'result': {}}))
                if not allowed:
                    with self.assertRaisesRegex(RuntimeError, 'Unrelated'):experiment.recover(self.directory, self.backend)
                    self.settings.write_bytes(prepared)
                experiment.recover(self.directory, self.backend);self.assert_restored();(self.debug / 'response.json').unlink()

    def test_campaign_settings_reject_other_values_duplicate_keys_and_profile_changes(self):
        self.campaign_fixture()
        changes = [lambda s: s.replace('<SoundVolume>0.5', '<SoundVolume>0.6'),
                   lambda s: s.replace('<WindowWidth>1280', '<WindowWidth>-1'),
                   lambda s: s.replace('<unlockAlpha>False', '<unlockAlpha>true'),
                   lambda s: s.replace('</GameSettings>', '<unlockAlpha>True</unlockAlpha></GameSettings>'),
                   lambda s: s.replace('<CustomDataPath>', '<CustomDataPath>different'),
                   lambda s: s.replace('<UseCustomDataPath>True', '<UseCustomDataPath>False'),
                   lambda s: s.replace('<SoundVolume>', '<SoundVolume changed="true">')]
        for i, change in enumerate(changes):
            with self.subTest(change=i):
                self.directory = self.root / ('unrelated-settings-' + str(i))
                with self.assertRaisesRegex(RuntimeError, 'Unrelated'):
                    with self.context(campaign_settings=True):
                        prepared = self.settings.read_bytes();changed = change(prepared.decode()).encode();self.settings.write_bytes(changed)
                self.assertEqual(self.settings.read_bytes(), changed);self.assertTrue(self.claim.exists())
                self.settings.write_bytes(prepared);experiment.recover(self.directory, self.backend);self.assert_restored()
        prepared = self.original[self.settings].replace(b'<unlockAlpha>False', b'<unlockAlpha>True')
        self.assertFalse(experiment.campaign_settings_match(prepared, self.original[self.settings]))

    def test_hard_exit_between_mkdir_and_inode_persist_recovers_empty_owned_directory(self):
        for name in ('backup', 'profile'):
            with self.subTest(directory=name):
                self.directory = self.root / ('crash-' + name)
                pid = os.fork()
                if pid == 0:
                    original = experiment.Experiment.persist
                    def crash(run):
                        if run.record['directories'].get(name) is not None:os._exit(77)
                        original(run)
                    with patch.object(experiment.Experiment, 'persist', crash):
                        with self.context():os._exit(78)
                    os._exit(79)
                _, status = os.waitpid(pid, 0);self.assertEqual(os.waitstatus_to_exitcode(status), 77)
                self.assertIsNone(self.read()['directories'][name])
                for path, data in self.original.items():self.assertEqual(path.read_bytes(), data)
                experiment.recover(self.directory, self.backend);self.assert_restored()

    def test_profile_name_preserves_probe_prefix_and_rejects_escape(self):
        name = 'cw3-unlocked-20261105-owned'
        with self.context(profile_name=name) as run:
            self.assertEqual(run.profile.parent, self.directory);self.assertEqual(run.profile.name, name)
            self.assertIn('/' + name, self.settings.read_text())
        self.assert_restored()
        for name in ('..', '../outside', '/outside', 'backup', 'journal.json'):
            with self.subTest(name=name):
                self.directory = self.root / 'invalid'
                with self.assertRaisesRegex(ValueError, 'basename'):
                    with self.context(profile_name=name):pass
                self.assertFalse(self.directory.exists())

    def test_replaced_owned_directories_are_not_written_or_deleted(self):
        retained = self.root / 'retained'
        with self.assertRaisesRegex(RuntimeError, 'ownership changed'):
            with self.context():
                self.directory.rename(retained)
                self.directory.mkdir();(self.directory / 'unrelated').write_text('keep')
        self.assertEqual(list(self.directory.iterdir()), [self.directory / 'unrelated'])
        self.assertEqual((self.directory / 'unrelated').read_text(), 'keep');self.assertTrue(self.claim.exists())
        (self.directory / 'unrelated').unlink();self.directory.rmdir();retained.rename(self.directory)
        experiment.recover(self.directory, self.backend);self.assert_restored()

    def test_cleanup_failure_keeps_incomplete_journal_and_recover_finishes(self):
        with patch.object(experiment.shutil, 'rmtree', side_effect=OSError('cleanup failed')):
            with self.assertRaisesRegex(OSError, 'cleanup failed'):
                with self.context():pass
        self.assertEqual(self.read()['phase'], 'restored');self.assertTrue(self.claim.exists())
        experiment.recover(self.directory, self.backend);self.assert_restored()


if __name__ == '__main__':unittest.main()
