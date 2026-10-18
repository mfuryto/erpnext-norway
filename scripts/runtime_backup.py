"""Coordinate a native ERPNext backup; no alternative database or file format."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import uuid


APP_SERVICES = {"backend", "frontend", "websocket", "scheduler", "queue-long", "queue-short"}
WRITER_SERVICES = {"backend", "queue-long", "queue-short"}
SITE = "/home/frappe/frappe-bench/sites/accounting"


class Runtime:
    def __init__(self, root, log):
        self.root, self.log = root, log
        self.prefix = None

    def call(self, args, capture=False):
        result = subprocess.run(args, cwd=self.root, text=True,
                                stdout=subprocess.PIPE if capture else self.log, stderr=self.log)
        if result.returncode:
            raise RuntimeError("Runtime command failed; details are in the private backup log.")
        return result.stdout if capture else None

    def compose(self, *args, capture=False):
        return self.call([*self.prefix, *args], capture=capture)

    def inspect(self):
        ids = self.call([
            "docker", "ps", "--filter", f"label=com.docker.compose.project.working_dir={self.root}",
            "--filter", "label=com.docker.compose.service=backend", "--format", "{{.ID}}",
        ], capture=True).split()
        if len(ids) != 1:
            raise RuntimeError("Expected exactly one running backend for this working directory.")
        backend = json.loads(self.call(["docker", "inspect", ids[0]], capture=True))[0]
        self.backend_id = backend["Id"]
        project = backend["Config"]["Labels"]["com.docker.compose.project"]
        self.prefix = ["docker", "compose", "--env-file", str(self.root / "deploy/.env"),
                       "-p", project, "-f", str(self.root / "compose.yaml")]
        config = json.loads(self.compose("config", "--format", "json", capture=True))
        if config["services"]["backend"]["image"] != backend["Config"]["Image"]:
            raise RuntimeError("Compose and running backend images differ. Back up before changing the runtime configuration.")
        running = set(self.compose("ps", "--status", "running", "--services", capture=True).split())
        if "backend" not in running:
            raise RuntimeError("Backend is not running.")
        services = sorted(APP_SERVICES & running)
        ids = self.compose("ps", "--status", "running", "--quiet", capture=True).split()
        containers = json.loads(self.call(["docker", "inspect", *ids], capture=True))
        images = {}
        for container in containers:
            service = container["Config"]["Labels"]["com.docker.compose.service"]
            image = container["Config"]["Image"]
            if image != config["services"][service]["image"]:
                raise RuntimeError("Compose and running service images differ. Back up before updating runtime configuration.")
            images[service] = {"image": image, "id": container["Image"]}
        return services, {"project": project, "backend_image": backend["Config"]["Image"],
                          "backend_image_id": backend["Image"], "running_app_services": services,
                          "images": images}

    def prepare(self, name):
        code = """import pathlib, shutil, sys
site = pathlib.Path('sites/accounting')
target = site / 'private/runtime-backups' / sys.argv[1]
target.parent.mkdir(mode=0o700, exist_ok=True)
target.mkdir(mode=0o700)
shutil.copy2(site / 'site_config.json', target / 'site_config.before.json')
shutil.copy2('sites/common_site_config.json', target / 'common_site_config.json')
"""
        self.compose("exec", "-T", "backend", "env/bin/python", "-c", code, name)

    def maintenance(self):
        self.compose("exec", "-T", "backend", "bench", "--site", "accounting", "set-maintenance-mode", "on")

    def stop(self, services):
        # Close entry points and scheduling first, then drain accounting writers.
        non_writers = sorted(set(services) - WRITER_SERVICES)
        writers = sorted(set(services) & WRITER_SERVICES)
        if non_writers:
            self.compose("stop", "--timeout", "15", *non_writers)
        self.compose("stop", "--timeout", "300", *writers)
        ids = self.compose("ps", "--all", "--quiet", *services, capture=True).split()
        stopped = json.loads(self.call(["docker", "inspect", *ids], capture=True))
        if any(item["State"]["Running"] or item["State"]["OOMKilled"] or
               (item["Config"]["Labels"]["com.docker.compose.service"] in WRITER_SERVICES and
                item["State"]["ExitCode"] == 137) for item in stopped):
            raise RuntimeError("An app service did not stop cleanly. Backup aborted; inspect jobs before retrying.")

    def backup(self, name):
        target = f"{SITE}/private/runtime-backups/{name}"
        self.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "backend",
                     "bench", "--site", "accounting", "backup", "--with-files", "--ignore-backup-conf",
                     "--backup-path-db", f"{target}/database.sql.gz",
                     "--backup-path-files", f"{target}/public.tar",
                     "--backup-path-private-files", f"{target}/private.tar",
                     "--backup-path-conf", f"{target}/site_config.json")

    def export(self, name, destination):
        native = destination / "native"
        native.mkdir(mode=0o700)
        self.call(["docker", "cp", f"{self.backend_id}:{SITE}/private/runtime-backups/{name}/.", str(native)])
        for filename in ("database.sql.gz", "public.tar", "private.tar", "site_config.json",
                         "site_config.before.json", "common_site_config.json"):
            if not (native / filename).is_file() or not (native / filename).stat().st_size:
                raise RuntimeError("Native backup is incomplete; required artifact is missing or empty.")
        before = json.loads((native / "site_config.before.json").read_text())
        saved = json.loads((native / "site_config.json").read_text())
        for key in ("db_name", "db_password", "encryption_key"):
            if not before.get(key) or before[key] != saved.get(key):
                raise RuntimeError("Native backup did not preserve the site's database identity or encryption key.")

    def restore_maintenance(self, name):
        # Restore only maintenance state, retaining any native backup-key changes.
        code = """import json, pathlib, sys
site = pathlib.Path('sites/accounting')
original = json.loads((site / 'private/runtime-backups' / sys.argv[1] / 'site_config.before.json').read_text())
path = site / 'site_config.json'
current = json.loads(path.read_text())
if 'maintenance_mode' in original:
    current['maintenance_mode'] = original['maintenance_mode']
else:
    current.pop('maintenance_mode', None)
temporary = path.with_suffix('.backup-resume.json')
temporary.write_text(json.dumps(current, indent=1))
temporary.chmod(path.stat().st_mode & 0o777)
temporary.replace(path)
"""
        self.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "backend",
                     "env/bin/python", "-c", code, name)

    def start(self, services):
        # Reuse native health waiting without recreating any existing container.
        self.compose("up", "-d", "--no-recreate", "--no-deps", "--pull", "never", "--no-build",
                     "--wait", "--wait-timeout", "300", *services)


def take_backup(runtime, name, destination, resume=True):
    services, metadata = runtime.inspect()
    runtime.prepare(name)
    # Once maintenance is attempted, always restore the original state, even on failure.
    complete = False
    try:
        runtime.maintenance()
        runtime.stop(services)
        runtime.backup(name)
        runtime.export(name, destination)
        complete = True
    finally:
        if resume or not complete:
            runtime.restore_maintenance(name)
            runtime.start(services)
    return metadata


@contextmanager
def runtime_lock(root):
    fd = os.open(root / ".runtime.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another runtime operation is active.") from None
        yield


def write_backup(root, name, runtime=None, resume=True):
    backups = root / "backups"
    if backups.is_symlink():
        raise RuntimeError("The private backups directory must not be a symbolic link.")
    backups.mkdir(mode=0o700, exist_ok=True)
    backups.chmod(0o700)
    destination = backups / name
    destination.mkdir(mode=0o700)
    with (destination / "runtime.log").open("w") as log:
        (destination / "runtime.log").chmod(0o600)
        shutil.copyfile(root / "deploy/.env", destination / "runtime.env")
        (destination / "runtime.env").chmod(0o600)
        shutil.copyfile(root / "compose.yaml", destination / "compose.yaml")
        runtime = runtime or Runtime(root, log)
        runtime.log = log
        metadata = take_backup(runtime, name, destination, resume=resume)
    try:
        metadata.update({"complete": True, "runtime_resumed": resume, "site_backup_path": f"{SITE}/private/runtime-backups/{name}"})
        (destination / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
        hashes = []
        for path in sorted(destination.rglob("*")):
            path.chmod(0o700 if path.is_dir() else 0o600)
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                hashes.append(f"{digest}  {path.relative_to(destination)}\n")
        (destination / "SHA256SUMS").write_text("".join(hashes))
        (destination / "SHA256SUMS").chmod(0o600)
    except BaseException:
        if not resume:
            # Sealing can fail after the native snapshot succeeded. Reopen the
            # log before restoring the original runtime; it was closed above.
            with (destination / "runtime.log").open("a") as log:
                runtime.log = log
                runtime.restore_maintenance(name)
                runtime.start(metadata["running_app_services"])
        raise
    return destination, metadata


def main():
    parser = argparse.ArgumentParser(description="Native ERPNext backup with private runtime configuration")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Existing Compose working directory; configuration is never regenerated")
    parser.add_argument("--name", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.name):
        parser.error("Backup name must contain only letters, numbers, underscores and hyphens.")
    root = args.root.resolve()
    def interrupted(signum, frame):
        raise KeyboardInterrupt("Runtime operation interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    with runtime_lock(root):
        destination, metadata = write_backup(root, args.name)
        print(f"Native backup complete; original services and maintenance state restored: backups/{args.name}")


if __name__ == "__main__":
    main()
