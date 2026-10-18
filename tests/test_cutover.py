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
        self.state = dict(legacy_root=str(self.root / 'legacy'), compose_project='legacy-accounting', config_files=[str(self.root / 'legacy/deploy/compose.yaml')], working_dir=str(self.root / 'legacy/deploy'), legacy_ip='127.0.0.1', legacy_port=8088)
        for key, value in [('ROOT', self.root), ('ENV', self.env), ('STATE', self.root / '.cutover.json')]:
            patcher = patch.object(cutover, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_success_freezes_old_writes_before_backup_and_retains_credentials(self):
        calls = []
        with patch.object(cutover, 'command', side_effect=lambda args, **kw: calls.append([str(a) for a in args]) or ''), patch.object(cutover, 'ready'):
            cutover.switch(self.state)
        backup = next(i for i, c in enumerate(calls) if c[0] == 'bash')
        stop = next(i for i, c in enumerate(calls) if c[-2:] == ['stop', 'web'])
        replacement = next(i for i, c in enumerate(calls) if '--force-recreate' in c)
        self.assertLess(stop, backup)
        self.assertLess(backup, replacement)
        self.assertEqual(cutover.read_env(self.env)['HTTP_PORT'], '8088')
        self.assertEqual(cutover.read_env(self.env)['DB_ROOT_PASSWORD'], 'synthetic-secret')
        self.assertEqual(self.state['status'], 'active')
        self.assertFalse(any('down' in c or '-v' in c for c in calls))
        self.assertEqual(calls[-1][-1], 'stop')

    def test_backup_failure_restores_legacy_without_rebinding_new_frontend(self):
        calls = []
        def run(args, **kw):
            args = [str(a) for a in args]
            calls.append(args)
            if args[0] == 'bash':
                raise RuntimeError('Synthetic backup failure')
            return ''
        with patch.object(cutover, 'command', side_effect=run), patch.object(cutover, 'ready'):
            with self.assertRaisesRegex(RuntimeError, 'backup failure'):
                cutover.switch(self.state)
        self.assertEqual(self.state['status'], 'rolled_back')
        self.assertEqual(cutover.read_env(self.env)['HTTP_PORT'], '18088')
        self.assertFalse(any('--force-recreate' in c for c in calls))
        self.assertEqual(calls[-1][-5:], ['up', '-d', '--wait', '--wait-timeout', '300'])

    def test_new_frontend_failure_releases_endpoint_and_restarts_original_project(self):
        calls = []
        def run(args, **kw):
            args = [str(a) for a in args]
            calls.append(args)
            if '--force-recreate' in args:
                raise RuntimeError('Synthetic new endpoint failure')
            return ''
        with patch.object(cutover, 'command', side_effect=run), patch.object(cutover, 'ready'):
            with self.assertRaisesRegex(RuntimeError, 'endpoint failure'):
                cutover.switch(self.state)
        release = next(i for i, c in enumerate(calls) if c[-2:] == ['stop', 'frontend'])
        resume = next(i for i, c in enumerate(calls) if c[-5:] == ['up', '-d', '--wait', '--wait-timeout', '300'])
        self.assertLess(release, resume)
        self.assertIn('legacy-accounting', calls[resume])
        self.assertEqual(self.state['status'], 'rolled_back')

    def test_same_port_refused_before_stopping_any_service(self):
        self.state['legacy_port'] = 18088
        with patch.object(cutover, 'command') as run:
            with self.assertRaisesRegex(RuntimeError, 'different local port'):
                cutover.switch(self.state)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
