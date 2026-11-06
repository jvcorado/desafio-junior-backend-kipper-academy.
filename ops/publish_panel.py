#!/usr/bin/env python3
"""Publish one authenticated HTTPS route using the existing Traefik host proxy.

Default: plan only. --preflight checks official images and private proxy config.
--apply creates a dedicated evaluation credential and only the Kipper container.
DNS A kipper.jayv.cloud must be created separately, without replacing other records.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOST = 'kipper.jayv.cloud'
CONTAINER = 'kipper-panel-proxy'
TRAEFIK = 'traefik-yvwt-traefik-1'
NGINX = 'nginx:stable-alpine'
HTPASSWD = 'httpd:2.4-alpine'
PRIVATE = Path('/etc/kipper-triagem')
ACCESS = PRIVATE / 'panel-access.json'
OPERATOR = Path('/home/deploy/kipper-triagem-staging/painel-acesso.txt')


def run(command, input=None):
    result = subprocess.run(command, input=input, text=True, capture_output=True)
    if result.returncode:
        # Never include argv: authentication hashes can be Docker label arguments.
        raise RuntimeError('Operation failed: ' + command[0] + ': ' + result.stderr[-1800:])
    return result.stdout.strip()


def write_exclusive(path, text, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'w') as out:
        out.write(text)


def image_digest(image):
    run(['docker', 'pull', image])
    return json.loads(run(['docker', 'image', 'inspect', image]))[0]['RepoDigests'][0]


def container_args(image, config):
    return ['--network', 'host', '--user', '101:101', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges=true', '--read-only',
        '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777',
        '--memory', '64m', '--cpus', '0.5', '--pids-limit', '64',
        '--mount', 'type=bind,src=' + str(config) + ',dst=/etc/nginx/nginx.conf,readonly',
        '--entrypoint', 'nginx', image]


def probe_private_proxy(image, config):
    name = 'kipper-panel-preflight'
    checks = {}
    run(['docker', 'run', '--rm', '-d', '--name', name, '--label', 'traefik.enable=false'] +
        container_args(image, config) + ['-g', 'daemon off;'])
    try:
        def request(path, origin=None, data=None, host=HOST):
            headers = {'Host': host, 'Content-Type': 'application/json'}
            if origin is not None: headers['Origin'] = origin
            req = Request('http://127.0.0.1:18083' + path, data=data, headers=headers)
            try:
                with urlopen(req, timeout=5) as response: return response.status
            except HTTPError as error: return error.code
        for attempt in range(20):
            try:
                checks['privateBackendReachable'] = request('/api/config') == 200
                break
            except URLError:
                if attempt == 19: raise
                time.sleep(0.2)
        checks['foreignOriginRejected'] = request('/api/config', 'https://example.org') == 403
        checks['unexpectedHostRejected'] = request('/api/config', host='localhost') == 421
        checks['transportIngressNotPublished'] = request('/api/events', 'https://' + HOST, b'{}') == 403
        checks['sameOriginReachesJavaValidation'] = request('/api/manual-events', 'https://' + HOST, b'{}') == 400
        if not all(checks.values()): raise RuntimeError('Private proxy boundary check failed: ' + str(checks))
        return checks
    finally:
        run(['docker', 'stop', '--time', '2', name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--username', default='mentora', help='Dedicated evaluation login; not a shell account')
    parser.add_argument('--password-file', type=Path, help='Optional operator-supplied password in a private mode-600 file; never pass a password as an argument')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--preflight', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    username = args.username
    if not re.fullmatch(r'[A-Za-z0-9@._-]{1,120}', username):
        raise SystemExit('Invalid evaluation username')
    source = args.config.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.sha256:
        raise SystemExit('Configuration checksum mismatch')
    plan = dict(url='https://' + HOST, dns=dict(type='A',name='kipper',value='187.41.101.68',ttl=300),
        login='Dedicated evaluation account; bcrypt cost 12; no credentials in repository or output',
        tls='Existing Traefik letsencrypt resolver',backend='127.0.0.1:18080, unchanged',
        privateProxy='127.0.0.1:18083', publicPorts='Existing 80/443 only',
        container=CONTAINER, scope='Evaluation account can use the master panel and its human actions',
        secrets='Root-only JSON; operator copy mode 600, outside Git',
        rollback='Remove only kipper-panel-proxy; private backend and WhatsApp remain running')
    if not (args.preflight or args.apply):
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    if os.geteuid() != 0:
        raise SystemExit('Run on the VPS host using the authorized administrative channel')
    proxy = json.loads(run(['docker', 'inspect', TRAEFIK]))[0]
    if proxy['HostConfig']['NetworkMode'] != 'host':
        raise SystemExit('Existing Traefik does not use host networking')
    if '--providers.docker=true' not in proxy['Config']['Cmd']:
        raise SystemExit('Existing Docker provider not confirmed')
    if run(['docker', 'ps', '-a', '--filter', 'name=^/' + CONTAINER + '$', '--format', '{{.ID}}']):
        raise SystemExit('Kipper public proxy already exists; inspect instead of repeating')
    if ACCESS.exists() or OPERATOR.exists():
        raise SystemExit('Credential marker exists; inspect partial deployment rather than rotating')
    with socket.socket() as check:
        check.bind(('127.0.0.1', 18083))
    if run(['systemctl', 'is-active', 'kipper-triagem.service']) != 'active':
        raise SystemExit('Private Kipper backend is not active')
    nginx_image = image_digest(NGINX)
    password_image = image_digest(HTPASSWD)
    preflight = Path('/var/lib/kipper-triagem/public-nginx-preflight.conf')
    preflight.write_bytes(source); preflight.chmod(0o644)
    run(['docker', 'run', '--rm'] + container_args(nginx_image, preflight) + ['-t'])
    if args.preflight:
        checks = probe_private_proxy(nginx_image, preflight)
        print(json.dumps(dict(preflight=True,configSha256=args.sha256,nginxImage=nginx_image,
            hashToolImage=password_image,checks=checks,plan=plan), ensure_ascii=False, indent=2)); return
    # No shell or command-line password. Authentication is installed before routing.
    password = secrets.token_urlsafe(24)
    if args.password_file:
        if args.password_file.is_symlink() or not args.password_file.is_file() or args.password_file.stat().st_mode & 0o077:
            raise SystemExit('Password input must be a regular private mode-600 file')
        password = args.password_file.read_text().rstrip('\r\n')
        if not 8 <= len(password.encode()) <= 72 or '\n' in password or '\r' in password:
            raise SystemExit('Password must be 8-72 bytes and a single line')
    password_hash = run(['docker', 'run', '--rm', '-i', '--network', 'none', '--entrypoint', 'htpasswd',
        password_image, '-niBC', '12', username], input=password + '\n')
    if not password_hash.startswith(username + ':$2'):
        raise RuntimeError('Expected bcrypt htpasswd output')
    write_exclusive(ACCESS, json.dumps(dict(url='https://' + HOST,username=username,password=password),indent=2)+'\n')
    write_exclusive(OPERATOR, 'Painel Kipper\nURL: https://' + HOST + '\nUsuário: ' + username + '\nSenha: ' + password +
        '\n\nAcesso de avaliação ao painel master. Compartilhe somente com a mentora.\n')
    os.chown(OPERATOR, 1000, 1000)
    config = PRIVATE / 'public-nginx.conf'
    write_exclusive(config, source.decode(), 0o644)
    labels = {
        'traefik.enable':'true',
        'traefik.http.routers.kipper-panel.rule':'Host(`' + HOST + '`)',
        'traefik.http.routers.kipper-panel.entrypoints':'websecure',
        'traefik.http.routers.kipper-panel.tls':'true',
        'traefik.http.routers.kipper-panel.tls.certresolver':'letsencrypt',
        'traefik.http.routers.kipper-panel.service':'kipper-panel',
        'traefik.http.routers.kipper-panel.middlewares':'kipper-rate,kipper-login',
        'traefik.http.services.kipper-panel.loadbalancer.server.port':'18083',
        'traefik.http.middlewares.kipper-login.basicauth.users':password_hash,
        'traefik.http.middlewares.kipper-login.basicauth.removeheader':'true',
        'traefik.http.middlewares.kipper-login.basicauth.realm':'Kipper - avaliacao',
        'traefik.http.middlewares.kipper-rate.ratelimit.average':'10',
        'traefik.http.middlewares.kipper-rate.ratelimit.burst':'20'}
    command = ['docker', 'run', '-d', '--name', CONTAINER, '--restart', 'unless-stopped']
    for key,value in labels.items(): command += ['--label', key + '=' + value]
    run(command + container_args(nginx_image, config) + ['-g', 'daemon off;'])
    state = json.loads(run(['docker', 'inspect', CONTAINER]))[0]
    if not state['State']['Running']:
        raise RuntimeError('Public proxy not running; inspect before retrying')
    if args.password_file:
        args.password_file.unlink()
    result = dict(installedAt=datetime.now(timezone.utc).isoformat(),url='https://' + HOST,
        dedicatedEvaluationLogin=True,passwordPrinted=False,nginxImage=nginx_image,
        configSha256=args.sha256,container=CONTAINER,operatorFile=str(OPERATOR),
        tlsVerified=False,authenticatedPanelVerified=False)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    write_exclusive(Path('/var/lib/kipper-triagem') / ('public-panel-' + stamp + '.json'),json.dumps(result,indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
