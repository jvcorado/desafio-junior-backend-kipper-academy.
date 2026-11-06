#!/usr/bin/env python3
"""Upgrade the existing private deployment to real Hermes inference and internal Kanban.

Run only on the VPS host. Input files are supplied explicitly and checksum-verified.
Default prints a plan; --apply creates a backup and changes only Kipper services.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import time
from urllib.request import urlopen

CONTAINER = 'hermes-agent-gj42-hermes-agent-1'


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError('Falha na etapa ' + args[0] + '; detalhes privados no host')
    return result


def write_private(path, text):
    temporary = path.with_suffix('.new')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(text)
    os.replace(temporary,path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('jar','worker','bridge'):
        parser.add_argument('--'+name, required=True, type=Path)
        parser.add_argument('--'+name+'-sha256', required=True)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    for name in ('jar','worker','bridge'):
        if hashlib.sha256(getattr(args,name).read_bytes()).hexdigest() != getattr(args,name+'_sha256'):
            raise SystemExit('Checksum inválido: '+name)
    if not args.apply:
        print(json.dumps(dict(ai='Hermes openai-codex/gpt-6.1-sol; credenciais permanecem no Hermes',
            delivery='Kanban interno',migration='Flyway V4',backend='127.0.0.1:18080',
            inference='127.0.0.1:18082',ingress='gateway Docker privado:18081, token próprio, origem única, somente chamados WhatsApp Kipper',
            backup='dump PostgreSQL e cópias privadas da configuração antes da alteração'),ensure_ascii=False,indent=2))
        return
    if os.geteuid() != 0:
        raise SystemExit('Execute no host da VPS pelo canal autorizado')
    settings = Path('/etc/kipper-triagem')
    if (settings/'bridge.json').exists():
        raise SystemExit('Integração já instalada: inspecione o estado antes de repetir')
    network = json.loads(run(['docker','inspect',CONTAINER],text=True).stdout)[0]['NetworkSettings']['Networks']['hermes-agent-gj42_default']
    gateway_ip, container_ip = network['Gateway'], network['IPAddress']
    for address,port in [('127.0.0.1',18082),(gateway_ip,18081)]:
        with socket.socket() as probe:
            probe.bind((address,port))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backups = Path('/var/backups/kipper-triagem')
    backup = backups/('triagem_java-pre-agent-'+stamp+'.dump')
    fd = os.open(backup, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output:
        result = subprocess.run(['docker','exec','pulsepay-db-postgres-1','pg_dump','-U','postgres','-Fc','triagem_java'],stdout=output,stderr=subprocess.PIPE)
    if result.returncode or not backup.stat().st_size:
        raise RuntimeError('Backup não confirmado')
    with backup.open('rb') as archive:
        run(['docker','exec','-i','pulsepay-db-postgres-1','pg_restore','--list'],stdin=archive)
    unit = Path('/etc/systemd/system/kipper-triagem.service')
    runtime = settings/'runtime.env'
    for source in (unit,runtime):
        destination = backups/(source.name+'.pre-agent-'+stamp)
        shutil.copyfile(source,destination)
        destination.chmod(0o600)
    release = Path('/opt/kipper-triagem/releases')/(args.jar_sha256+'.jar')
    shutil.copyfile(args.jar,release)
    release.chmod(0o444)
    worker_dir = '/opt/kipper-triagem-runtime'
    run(['docker','exec','--user','0',CONTAINER,'mkdir','-p',worker_dir])
    run(['docker','cp',str(args.worker),CONTAINER+':'+worker_dir+'/ai_worker.py'])
    run(['docker','exec','--user','0',CONTAINER,'chown','-R','0:0',worker_dir])
    run(['docker','exec','--user','0',CONTAINER,'chmod','-R','a+rX,go-w',worker_dir])
    bridge = Path('/opt/kipper-triagem/private_bridge.py')
    shutil.copyfile(args.bridge,bridge)
    bridge.chmod(0o444)
    private = dict(ai_key=secrets.token_urlsafe(48),ingress_key=secrets.token_urlsafe(48),gateway_ip=gateway_ip,container_ip=container_ip)
    write_private(settings/'bridge.json',json.dumps(private))
    values = dict(line.split('=',1) for line in runtime.read_text().splitlines() if line and not line.startswith('#'))
    values.update(AI_MODE='http',DELIVERY_MODE='panel',AI_URL='http://127.0.0.1:18082/v1/chat/completions',AI_API_KEY=private['ai_key'],AI_MODEL='gpt-6.1-sol')
    write_private(runtime,''.join(k+'='+v+'\n' for k,v in values.items()))
    original = unit.read_text()
    updated,count = re.subn(r'/opt/kipper-triagem/releases/[a-f0-9]{64}\.jar',str(release),original)
    if count != 1:
        raise RuntimeError('Unidade inesperada; configurar manualmente a partir do backup')
    unit.write_text(updated)
    bridge_unit = Path('/etc/systemd/system/kipper-triagem-bridge.service')
    bridge_unit.write_text('''[Unit]
Description=Kipper private support and Hermes inference bridge
After=docker.service network.target
Requires=docker.service
[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/kipper-triagem/private_bridge.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
RestrictAddressFamilies=AF_UNIX AF_INET
UMask=0077
[Install]
WantedBy=multi-user.target
''')
    run(['systemctl','daemon-reload'])
    run(['systemctl','enable','--now','kipper-triagem-bridge.service'])
    run(['systemctl','restart','kipper-triagem.service'])
    for attempt in range(45):
        try:
            with urlopen('http://127.0.0.1:18080/api/config',timeout=2) as response:
                config = json.load(response)
            if config == dict(aiMode='http',deliveryMode='panel'):
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('Backend não confirmou nova configuração; consulte backups privados')
    receipt = dict(verifiedAt=datetime.now(timezone.utc).isoformat(),jarSha256=args.jar_sha256,
                   workerSha256=args.worker_sha256,bridgeSha256=args.bridge_sha256,
                   config=config,backup=str(backup),inferenceVerified=False,
                   whatsappConnected=False,services=['kipper-triagem.service','kipper-triagem-bridge.service'])
    target=Path('/var/lib/kipper-triagem')/('agent-install-'+stamp+'.json')
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    target.chmod(0o600)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
