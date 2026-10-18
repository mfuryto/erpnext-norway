#!/usr/bin/env python3
"""Stop the old Compose installation and reuse its HTTP endpoint. No data is deleted."""
import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from init_runtime import read_env

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'deploy/.env'


def command(args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def compose():
    return ['docker', 'compose', '--env-file', ENV, '-p', 'erpnext-norway', '-f', ROOT / 'compose.yaml']


def ready(ip, port):
    if ip == '0.0.0.0':
        ip = '127.0.0.1'
    elif ip == '::':
        ip = '::1'
    host = f'[{ip}]' if ':' in ip else ip
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(30):
        try:
            with opener.open(f'http://{host}:{port}/api/method/ping', timeout=5) as response:
                if response.status == 200 and json.load(response).get('message') == 'pong':
                    return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError('ERPNext did not answer its readiness endpoint')


def discover(legacy_root):
    ids = command(['docker', 'ps', '-a', '-q', '--filter', 'label=com.docker.compose.service=web']).split()
    matches = []
    for cid in ids:
        container = json.loads(command(['docker', 'inspect', cid]))[0]
        labels = container['Config'].get('Labels') or {}
        files = [str(Path(f).resolve()) for f in labels.get('com.docker.compose.project.config_files', '').split(',') if f]
        env = dict(line.split('=', 1) for line in container['Config']['Env'] if '=' in line)
        if env.get('DOLI_DB_NAME') != 'accounting' or not files or not all(Path(f).is_relative_to(legacy_root) for f in files):
            continue
        bindings = container['HostConfig']['PortBindings'].get('80/tcp') or []
        if len(bindings) != 1:
            raise RuntimeError('Expected one Dolibarr HTTP binding; inspect bindings before switching')
        bind = bindings[0]
        ipaddress.ip_address(bind['HostIp'])
        old = ['docker', 'compose', '--project-directory', labels['com.docker.compose.project.working_dir'], '--env-file', legacy_root / 'deploy/.env', '-p', labels['com.docker.compose.project']]
        for filename in files:
            old += ['-f', filename]
        matches.append((old, bind['HostIp'], int(bind['HostPort'])))
    if len(matches) != 1:
        raise RuntimeError('Expected one persistent Dolibarr installation in the supplied directory')
    return matches[0]


def switch(legacy_root):
    old, ip, port = discover(legacy_root)
    settings = read_env(ENV)
    ready(settings['BIND_IP'], settings['HTTP_PORT'])
    command(old + ['config', '--quiet'])
    # Both sites use different data directories and databases. No backup or fallback is created.
    command(old + ['stop'])
    settings.update(BIND_IP=ip, HTTP_PORT=str(port))
    temp = ENV.with_suffix('.env.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{k}={v}\n' for k, v in settings.items()))
    os.replace(temp, ENV)
    command(compose() + ['up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '300', 'frontend'])
    ready(ip, port)
    print('ERPNext uses the original HTTP endpoint. Dolibarr is stopped; existing files remain untouched.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('legacy_root', type=Path)
    args = parser.parse_args()
    with open(ROOT / '.cutover.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        switch(args.legacy_root.resolve())


if __name__ == '__main__':
    main()
