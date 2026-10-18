import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('cutover', ROOT / 'scripts/cutover-from-dolibarr.py')
cutover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutover)


class CutoverContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / 'deploy/.env'
        self.env.parent.mkdir()
        self.env.write_text('PUBLIC_URL=https://accounting.invalid\nBIND_IP=127.0.0.1\nHTTP_PORT=18088\nDB_ROOT_PASSWORD=synthetic-secret\nADMIN_PASSWORD=synthetic-admin\n')
        self.old = ['docker', 'compose', '-p', 'legacy-accounting']
        for key, value in [('ROOT', self.root), ('ENV', self.env)]:
            patcher = patch.object(cutover, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_prepared_site_is_verified_before_stopping_old_services(self):
        events = []
        with patch.object(cutover, 'discover', return_value=(self.old, '127.0.0.1', 8088)), patch.object(cutover, 'command', side_effect=lambda args: events.append([str(a) for a in args]) or ''), patch.object(cutover, 'ready', side_effect=lambda ip, port: events.append(['ready', str(port)])):
            cutover.switch(self.root / 'legacy')
        self.assertEqual(events[0], ['ready', '18088'])
        stop = next(i for i, c in enumerate(events) if c[-1] == 'stop')
        replacement = next(i for i, c in enumerate(events) if '--force-recreate' in c)
        self.assertLess(stop, replacement)
        self.assertEqual(events[-1], ['ready', '8088'])
        settings = cutover.read_env(self.env)
        self.assertEqual(settings['HTTP_PORT'], '8088')
        self.assertEqual(settings['DB_ROOT_PASSWORD'], 'synthetic-secret')
        self.assertEqual(settings['ADMIN_PASSWORD'], 'synthetic-admin')
        self.assertFalse(any('backup' in ' '.join(c) or 'down' in c or '-v' in c for c in events))

    def test_unready_new_site_does_not_stop_old_services_or_change_settings(self):
        original = self.env.read_bytes()
        with patch.object(cutover, 'discover', return_value=(self.old, '127.0.0.1', 8088)), patch.object(cutover, 'ready', side_effect=RuntimeError('Not ready')), patch.object(cutover, 'command') as run:
            with self.assertRaisesRegex(RuntimeError, 'Not ready'):
                cutover.switch(self.root / 'legacy')
            run.assert_not_called()
        self.assertEqual(self.env.read_bytes(), original)

    def test_failed_frontend_does_not_run_unrequested_backup_or_fallback(self):
        calls = []
        def run(args):
            args = [str(a) for a in args]
            calls.append(args)
            if '--force-recreate' in args:
                raise RuntimeError('Synthetic startup failure')
            return ''
        with patch.object(cutover, 'discover', return_value=(self.old, '127.0.0.1', 8088)), patch.object(cutover, 'ready'), patch.object(cutover, 'command', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'startup failure'):
                cutover.switch(self.root / 'legacy')
        self.assertEqual(calls[-1][-1], 'frontend')
        self.assertFalse(any('backup' in ' '.join(c) or '--rollback' in c for c in calls))


if __name__ == '__main__':
    unittest.main()
