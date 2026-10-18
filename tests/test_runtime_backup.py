import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime_backup import runtime_lock, take_backup


class NativeRuntimeModel:
    def __init__(self, fail=None, maintenance=False):
        self.running = {"backend", "frontend"}  # Scheduler deliberately disabled beforehand.
        self.original_running = self.running.copy()
        self.mode = self.original_mode = maintenance
        self.fail = fail
        self.events = []

    def event(self, name):
        self.events.append(name)
        if self.fail == name:
            raise RuntimeError("injected failure")

    def inspect(self):
        self.event("inspect")
        return sorted(self.running), {"project": "synthetic"}

    def prepare(self, name):
        self.event("prepare")

    def maintenance(self):
        self.mode = True
        self.event("maintenance")

    def stop(self, services):
        self.running.remove("frontend")  # Model a partial stop if stop fails.
        self.event("stop")
        self.running.difference_update(services)

    def backup(self, name):
        assert not self.running and self.mode
        self.event("backup")

    def export(self, name, destination):
        self.event("export")

    def restore_maintenance(self, name):
        self.event("restore_maintenance")
        self.mode = self.original_mode

    def start(self, services):
        self.event("start")
        self.running.update(services)


class BackupContract(unittest.TestCase):
    def test_snapshot_stops_writers_and_restores_exact_original_services_and_mode(self):
        for initial_mode in (False, True):
            with self.subTest(maintenance=initial_mode):
                runtime = NativeRuntimeModel(maintenance=initial_mode)
                take_backup(runtime, "synthetic", Path("unused"))
                self.assertEqual(runtime.running, runtime.original_running)
                self.assertEqual(runtime.mode, initial_mode)
                self.assertNotIn("scheduler", runtime.running)
                self.assertLess(runtime.events.index("stop"), runtime.events.index("backup"))

    def test_partial_stop_backup_and_export_failure_restore_availability(self):
        for failure in ("maintenance", "stop", "backup", "export"):
            with self.subTest(failure=failure):
                runtime = NativeRuntimeModel(fail=failure)
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    take_backup(runtime, "synthetic", Path("unused"))
                self.assertEqual(runtime.running, runtime.original_running)
                self.assertFalse(runtime.mode)

    def test_preflight_failure_does_not_change_services_or_maintenance(self):
        runtime = NativeRuntimeModel(fail="inspect")
        with self.assertRaises(RuntimeError):
            take_backup(runtime, "synthetic", Path("unused"))
        self.assertEqual(runtime.events, ["inspect"])
        self.assertEqual(runtime.running, runtime.original_running)
        self.assertFalse(runtime.mode)

    def test_resume_failure_leaves_services_stopped_instead_of_opening_unknown_state(self):
        runtime = NativeRuntimeModel(fail="restore_maintenance")
        with self.assertRaises(RuntimeError):
            take_backup(runtime, "synthetic", Path("unused"))
        self.assertNotIn("start", runtime.events)
        self.assertTrue(runtime.mode)
        self.assertFalse(runtime.running)

    def test_concurrent_runtime_operation_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with runtime_lock(root):
                with self.assertRaisesRegex(RuntimeError, "Another runtime operation"):
                    with runtime_lock(root):
                        self.fail("second lock acquired")


if __name__ == "__main__":
    unittest.main()
