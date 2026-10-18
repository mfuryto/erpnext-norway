#!/usr/bin/env python3
"""Generate private runtime settings. Never reuse a legacy database or its credentials."""
import argparse
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def read_env(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip().strip("\"'")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-dolibarr', type=Path)
    parser.add_argument('--url')
    parser.add_argument('--port', type=int, default=18088)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / 'deploy/.env'
    if target.exists():
        raise SystemExit('Existing deploy/.env retained. No credentials changed.')
    url = args.url
    if not url and args.from_dolibarr:
        url = read_env(args.from_dolibarr / 'deploy/.env').get('PUBLIC_URL')
    parsed = urlsplit(url or '')
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/') or any(c.isspace() for c in url) or not 1024 <= args.port <= 65535:
        raise SystemExit('Supply a valid public URL and unprivileged port.')
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(f'PUBLIC_URL={url.rstrip("/")}\nBIND_IP=127.0.0.1\nHTTP_PORT={args.port}\nDB_ROOT_PASSWORD={secrets.token_hex(32)}\nADMIN_PASSWORD={secrets.token_hex(32)}\n')
    print('Private deploy/.env created. Credentials were not printed.')


if __name__ == '__main__':
    main()
