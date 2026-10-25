"""Failure contracts for the boundary between backup and schema migration."""
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from runtime_update import update, replace_image
from runtime_backup import take_backup, write_backup
from test_runtime_backup import NativeRuntimeModel

IMAGE = 'sha256:' + 'a' * 64


class UpdateRuntime:
    def __init__(self, fail=None):
        self.events = []
        self.fail = fail

    def call(self, args, capture=False):
        self.events.append(('call', args))
        if args[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([{'Id': IMAGE, 'Config': {'Labels': {'no.erpnext-norway.base': 'v16.52.1'}}}])

    def compose(self, *args, **kwargs):
        self.events.append(('compose', args))
        if self.fail and self.fail in str(args):
            raise RuntimeError('injected migration failure')

    def restore_maintenance(self, name):
        self.events.append(('restore', name))

    def start(self, services):
        self.events.append(('start', services))

    def stop(self, services):
        self.events.append(('stop', services))


class UpdateContract(unittest.TestCase):
    def fixture(self, root):
        (root / 'deploy').mkdir()
        original = 'DB_ROOT_PASSWORD=synthetic-only\nADMIN_PASSWORD=keep-this-value\nHTTP_PORT=12345\n'
        (root / 'deploy/.env').write_text(original)
        destination = root / 'backups/upgrade'
        destination.mkdir(parents=True)
        return original, destination

    def test_prepared_backup_keeps_writers_stopped_but_failure_restores_original_state(self):
        runtime = NativeRuntimeModel()
        take_backup(runtime, 'test', Path('unused'), resume=False)
        self.assertFalse(runtime.running)
        self.assertTrue(runtime.mode)
        for failure in ('maintenance', 'stop', 'backup', 'export'):
            runtime = NativeRuntimeModel(fail=failure)
            with self.assertRaises(RuntimeError):
                take_backup(runtime, 'test', Path('unused'), resume=False)
            self.assertEqual(runtime.running, runtime.original_running)
            self.assertEqual(runtime.mode, runtime.original_mode)

    def test_sealing_failure_after_snapshot_resumes_original_services(self):
        class RuntimeModel(NativeRuntimeModel):
            def inspect(self):
                services, metadata = super().inspect()
                metadata['running_app_services'] = services
                return services, metadata
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'deploy').mkdir()
            (root / 'deploy/.env').write_text('PRIVATE=synthetic-only')
            (root / 'compose.yaml').write_text('synthetic fixture')
            runtime = RuntimeModel()
            with patch('runtime_backup.hashlib.file_digest', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    write_backup(root, 'failure', runtime=runtime, resume=False)
            self.assertEqual(runtime.running, runtime.original_running)
            self.assertEqual(runtime.mode, runtime.original_mode)

    def test_invalid_target_does_not_start_backup_or_change_configuration(self):
        runtime = UpdateRuntime()
        with patch('runtime_update.write_backup') as backup:
            with self.assertRaises(RuntimeError):
                update(runtime, Path('unused'), 'mutable:latest', 'test')
            backup.assert_not_called()
        self.assertFalse(runtime.events)

    def test_previous_base_is_rejected_before_backup_or_site_changes(self):
        runtime = UpdateRuntime()
        with patch.object(runtime, 'call', return_value=json.dumps([
                {'Id': IMAGE, 'Config': {'Labels': {'no.erpnext-norway.base': 'v16.51.1'}}}])):
            with patch('runtime_update.write_backup') as backup:
                with self.assertRaisesRegex(RuntimeError, 'qualified pinned ERPNext base'):
                    update(runtime, Path('unused'), IMAGE, 'test')
                backup.assert_not_called()

    def test_configuration_write_failure_restores_original_runtime_before_migration(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original, destination = self.fixture(root)
            runtime = UpdateRuntime()
            with patch('runtime_update.write_backup', return_value=(destination, {'running_app_services': ['backend', 'frontend']})):
                with patch('runtime_update.write_environment', side_effect=[OSError('disk failure'), None]):
                    with self.assertRaises(OSError):
                        update(runtime, root, IMAGE, 'upgrade')
            self.assertEqual((root / 'deploy/.env').read_text(), original)
            self.assertTrue(any(event[0] == 'start' for event in runtime.events))
            self.assertFalse(any('install-app' in str(event) for event in runtime.events))

    def test_migration_failure_leaves_target_and_maintenance_stopped_without_old_image_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original, destination = self.fixture(root)
            runtime = UpdateRuntime(fail='install-app')
            def backup(*args, **kwargs):
                self.assertEqual((root / 'deploy/.env').read_text(), original)
                self.assertFalse(kwargs['resume'])
                return destination, {'running_app_services': ['backend', 'frontend']}
            with patch('runtime_update.write_backup', side_effect=backup):
                with self.assertRaises(RuntimeError):
                    update(runtime, root, IMAGE, 'upgrade')
            self.assertIn(f'ERP_APP_IMAGE={IMAGE}', (root / 'deploy/.env').read_text())
            self.assertTrue(any('set-maintenance-mode' in str(event) for event in runtime.events))
            self.assertTrue(any(event[0] == 'stop' for event in runtime.events))
            self.assertFalse(any(event[0] in ('start', 'restore') for event in runtime.events))

    def test_success_preserves_private_configuration_and_only_resumes_previous_services(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original, destination = self.fixture(root)
            runtime = UpdateRuntime()
            with patch('runtime_update.write_backup', return_value=(destination, {'running_app_services': ['backend', 'frontend']})):
                update(runtime, root, IMAGE, 'upgrade')
            self.assertEqual((root / 'deploy/.env').read_text(), original + f'ERP_APP_IMAGE={IMAGE}\n')
            starts = [event for event in runtime.events if event[0] == 'compose' and event[1][0] == 'up']
            self.assertEqual(starts[0][1][-2:], ('backend', 'frontend'))
            self.assertIn('--pull', starts[0][1])
            self.assertNotIn('scheduler', starts[0][1])
            self.assertEqual((destination / 'update.log').stat().st_mode & 0o777, 0o600)

    def test_duplicate_image_configuration_is_rejected_and_existing_value_replaced(self):
        with self.assertRaises(RuntimeError):
            replace_image('ERP_APP_IMAGE=x\nERP_APP_IMAGE=y\n', IMAGE)
        self.assertEqual(replace_image('KEY=preserved\nERP_APP_IMAGE=old\n', IMAGE),
                         f'KEY=preserved\nERP_APP_IMAGE={IMAGE}\n')


if __name__ == '__main__':
    unittest.main()
