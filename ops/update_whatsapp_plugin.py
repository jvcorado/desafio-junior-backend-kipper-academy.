#!/usr/bin/env python3
"""Update only the installed Kipper plugin, preserving a private backup first."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

CONTAINER = 'hermes-agent-gj42-hermes-agent-1'
TARGET = '/opt/data/profiles/kipper-triagem/plugins/kipper-support/__init__.py'


def run(command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != args.sha256:
        raise SystemExit('Source checksum mismatch')
    if not args.apply:
        print(json.dumps(dict(container=CONTAINER, target=TARGET, sha256=args.sha256, backup=True, reload='kipper-triagem only')))
        return
    if os.geteuid() != 0:
        raise SystemExit('Run on the VPS host through the authorized administrative channel')
    run(['docker', 'exec', '--user', '10000:10000', CONTAINER, 'test', '-f', TARGET])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/kipper-triagem') / ('whatsapp-plugin-' + stamp)
    backup.mkdir(mode=0o700)
    run(['docker', 'cp', CONTAINER + ':' + TARGET, str(backup / '__init__.py')])
    (backup / '__init__.py').chmod(0o600)
    run(['docker', 'cp', str(args.source), CONTAINER + ':' + TARGET])
    run(['docker', 'exec', '--user', '0', CONTAINER, 'chown', '10000:10000', TARGET])
    run(['docker', 'exec', '--user', '0', CONTAINER, 'chmod', '600', TARGET])
    actual = run(['docker', 'exec', '--user', '10000:10000', CONTAINER, 'sha256sum', TARGET]).split()[0]
    if actual != args.sha256:
        raise RuntimeError('Installed checksum mismatch; restore the private backup')
    code = "from pathlib import Path; import json; from gateway.control_socket import reload_gateway_plugins; print(json.dumps(reload_gateway_plugins(Path('/opt/data'), profile_home=Path('/opt/data/profiles/kipper-triagem'))))"
    reload_result = json.loads(run(['docker', 'exec', '--user', '10000:10000', '-e',
        'PYTHONPATH=/opt/hermes:/opt/hermes/.venv/lib/python3.14/site-packages', CONTAINER,
        '/opt/hermes/.venv/bin/python', '-c', code]))
    if not reload_result.get('reloaded'):
        raise RuntimeError('Plugin installed but reload not confirmed; inspect before retrying')
    result = dict(verifiedAt=datetime.now(timezone.utc).isoformat(), sha256=actual,
        backup=str(backup), profile='kipper-triagem', pluginReloaded=True)
    receipt = Path('/var/lib/kipper-triagem') / ('whatsapp-plugin-' + stamp + '.json')
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
