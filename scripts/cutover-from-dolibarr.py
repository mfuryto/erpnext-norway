#!/usr/bin/env python3
"""Switch an existing Compose endpoint, preserving the old database and files."""
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
STATE = ROOT / '.cutover.json'


def command(args, **kwargs):
    return subprocess.check_output([str(a) for a in args], text=True, **kwargs).strip()


def compose():
    return ['docker', 'compose', '--env-file', ENV, '-p', 'erpnext-norway', '-f', ROOT / 'compose.yaml']


def legacy_compose(state):
    result = ['docker', 'compose', '--project-directory', state['working_dir'], '--env-file', str(Path(state['legacy_root']) / 'deploy/.env'), '-p', state['compose_project']]
    for filename in state['config_files']:
        result += ['-f', filename]
    return result


def write_state(state):
    fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(state, stream, indent=2)


def set_endpoint(ip, port):
    ipaddress.ip_address(ip)
    if not 1 <= int(port) <= 65535:
        raise RuntimeError('Invalid port')
    settings = read_env(ENV)
    settings.update(BIND_IP=str(ip), HTTP_PORT=str(port))
    temp = ENV.with_suffix('.env.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{k}={v}\n' for k, v in settings.items()))
    os.replace(temp, ENV)


def ready(ip, port):
    if ip == '0.0.0.0':
        ip = '127.0.0.1'
    elif ip == '::':
        ip = '::1'
    host = f'[{ip}]' if ':' in ip else ip
    # Do not use an HTTP proxy for a local readiness test.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f'http://{host}:{port}/api/method/ping'
    for _ in range(30):
        try:
            with opener.open(url, timeout=5) as response:
                if response.status == 200 and json.load(response).get('message') == 'pong':
                    return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError('ERPNext did not answer its readiness endpoint')


def discover(legacy_root):
    candidates = command(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.service=web']).split()
    matches = []
    for cid in candidates:
        container = json.loads(command(['docker', 'inspect', cid]))[0]
        labels = container['Config'].get('Labels') or {}
        files = [str(Path(f).resolve()) for f in labels.get('com.docker.compose.project.config_files', '').split(',') if f]
        env = dict(line.split('=', 1) for line in container['Config']['Env'] if '=' in line)
        if env.get('DOLI_DB_NAME') != 'accounting' or not files or not all(Path(f).is_relative_to(legacy_root) for f in files):
            continue
        bindings = container['NetworkSettings']['Ports'].get('80/tcp') or []
        if len(bindings) != 1:
            raise RuntimeError('Expected exactly one published Dolibarr HTTP endpoint; inspect binding before switching')
        bind = bindings[0]
        ipaddress.ip_address(bind['HostIp'])
        matches.append(dict(legacy_root=str(legacy_root), compose_project=labels['com.docker.compose.project'], config_files=files, working_dir=labels['com.docker.compose.project.working_dir'], legacy_ip=bind['HostIp'], legacy_port=int(bind['HostPort'])))
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one running persistent Dolibarr installation in the supplied directory')
    return matches[0]


def rollback(state):
    # Free the old endpoint before restarting its original owner.
    command(compose() + ['stop', 'frontend'])
    set_endpoint(state['staging_ip'], state['staging_port'])
    command(legacy_compose(state) + ['up', '-d', '--wait', '--wait-timeout', '300'])
    state['status'] = 'rolled_back'
    write_state(state)
    # ERPNext data remains available; its frontend can be started on the staging port later.
    print('Dolibarr restarted. ERPNext data retained; its frontend is stopped.')


def switch(state):
    settings = read_env(ENV)
    state.update(staging_ip=settings['BIND_IP'], staging_port=int(settings['HTTP_PORT']), status='prepared')
    if (state['staging_ip'], state['staging_port']) == (state['legacy_ip'], state['legacy_port']):
        raise RuntimeError('Prepare ERPNext on a different local port first')
    ready(state['staging_ip'], state['staging_port'])
    old = legacy_compose(state)
    # Verify the original command while the old service is still available.
    command(old + ['config', '--quiet'])
    write_state(state)
    try:
        command(old + ['stop', 'web'])
        backup_env = dict(os.environ, NORWAY_COMPOSE_PROJECT=state['compose_project'], NORWAY_BACKUP_DIR=str(Path(state['legacy_root']) / 'backups'))
        command(['bash', Path(state['legacy_root']) / 'scripts/backup-installation.sh'], env=backup_env)
        state['status'] = 'backed_up'
        write_state(state)
        set_endpoint(state['legacy_ip'], state['legacy_port'])
        command(compose() + ['up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '300', 'frontend'])
        ready(state['legacy_ip'], state['legacy_port'])
        command(old + ['stop'])
        state['status'] = 'active'
        write_state(state)
    except BaseException:
        try:
            rollback(state)
        except Exception:
            print('Automatic rollback failed. Inspect local state and restart the original Compose project manually.')
        raise
    print('ERPNext now uses the original endpoint. Dolibarr stopped; its files and backups are retained.')
    print('Verify the public URL and reverse-proxy WebSocket forwarding before use.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('legacy_root', nargs='?', type=Path)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    with open(ROOT / '.cutover.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.rollback:
            if not STATE.exists():
                raise SystemExit('No recorded cutover')
            rollback(json.loads(STATE.read_text()))
        else:
            if STATE.exists() and json.loads(STATE.read_text()).get('status') in ('active', 'prepared', 'backed_up'):
                raise SystemExit('Existing cutover state; inspect it or use --rollback')
            if not args.legacy_root:
                parser.error('Supply the existing installation directory')
            switch(discover(args.legacy_root.resolve()))


if __name__ == '__main__':
    main()
