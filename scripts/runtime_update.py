"""Install/migrate the external app using native bench and a stopped full backup."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import tempfile
from datetime import datetime, timezone
import uuid

from runtime_backup import Runtime, runtime_lock, write_backup, APP_SERVICES


def replace_image(environment, image):
    lines = environment.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith("ERP_APP_IMAGE=")]
    if len(matches) > 1:
        raise RuntimeError("Duplicate ERP_APP_IMAGE configuration; inspect it before updating.")
    value = f"ERP_APP_IMAGE={image}\n"
    if matches:
        lines[matches[0]] = value
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(value)
    return "".join(lines)


def write_environment(path, contents):
    descriptor, temporary = tempfile.mkstemp(prefix=".runtime-update-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def update(runtime, root, image, name):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise RuntimeError("Use the immutable local image ID printed by build-app-image.sh.")
    info = json.loads(runtime.call(["docker", "image", "inspect", image], capture=True))[0]
    labels = info["Config"].get("Labels") or {}
    if labels.get("no.erpnext-norway.base") != "v16.51.1":
        raise RuntimeError("The target must use the qualified pinned ERPNext base.")
    image = info["Id"]
    # No mounted site and no network: inspect code before maintenance or DB changes.
    runtime.call(["docker", "run", "--rm", "--network", "none", "--entrypoint", "env/bin/python", image,
                  "-c", "import erpnext_norway, frappe, erpnext; assert frappe.__version__ == '16.52.0'; assert erpnext.__version__ == '16.51.1'"])
    environment_path = root / "deploy/.env"
    original = environment_path.read_text()
    configured = replace_image(original, image)
    destination, metadata = write_backup(root, name, runtime=runtime, resume=False)
    # Runtime.log belonged to the completed backup; reopen a separate private log.
    with (destination / "update.log").open("w") as log:
        (destination / "update.log").chmod(0o600)
        runtime.log = log
        migration_started = False
        try:
            write_environment(environment_path, configured)
            migration_started = True
            runtime.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "backend", "bash", "-euc",
                "ls -1 apps > sites/apps.txt; bench --site accounting install-app erpnext_norway; bench --site accounting migrate")
            runtime.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "backend", "bench", "--site", "accounting", "list-apps")
            runtime.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "create-site",
                            "env/bin/python", "/opt/runtime/module-visibility.py")
            runtime.restore_maintenance(name)
            runtime.compose("up", "-d", "--force-recreate", "--no-deps", "--pull", "never", "--no-build",
                            "--wait", "--wait-timeout", "300", *metadata["running_app_services"])
        except BaseException:
            if not migration_started:
                write_environment(environment_path, original)
                runtime.restore_maintenance(name)
                runtime.start(metadata["running_app_services"])
            else:
                # Never reopen an older image against a possibly migrated DB.
                runtime.compose("run", "--rm", "--no-deps", "-T", "--pull", "never", "backend", "bench",
                                "--site", "accounting", "set-maintenance-mode", "on")
                runtime.stop(sorted(APP_SERVICES))
            raise
    return destination


def main():
    parser = argparse.ArgumentParser(description="Back up existing runtime, then install/migrate the Norwegian app")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--image", required=True)
    parser.add_argument("--name", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-update-") + uuid.uuid4().hex[:8])
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.name):
        parser.error("Invalid backup name")
    def interrupted(signum, frame):
        raise KeyboardInterrupt("Runtime update interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    root = args.root.resolve()
    with runtime_lock(root):
        # A private preflight log exists even when target inspection fails.
        fd, filename = tempfile.mkstemp(prefix="erpnext-update-", suffix=".log")
        with os.fdopen(fd, "w") as log:
            try:
                destination = update(Runtime(root, log), root, args.image, args.name)
            except BaseException:
                print(f"Update failed. Inspect private log {filename} and backups/{args.name}/ locally; do not share them.")
                raise
        Path(filename).unlink()
    print(f"Native app install/migration completed. Previous runtime backup: {destination.relative_to(root)}")


if __name__ == "__main__":
    main()
