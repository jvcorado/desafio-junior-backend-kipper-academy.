#!/usr/bin/env python3
"""Allow only the existing Hermes container to reach the private Kipper ingress.

Plan by default. Does not enable/disable UFW, alter public ports or publish the panel.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

CONTAINER='hermes-agent-gj42-hermes-agent-1'
SOURCE='172.16.6.2'
DESTINATION='172.16.6.1'
PORT='18081'


def run(args):
    result=subprocess.run(args,capture_output=True,text=True,check=True)
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    command=['ufw','allow','in','proto','tcp','from',SOURCE,'to',DESTINATION,'port',PORT,'comment','kipper-triagem private ingress']
    plan=dict(source=SOURCE,destination=DESTINATION,port=int(PORT),protocol='tcp',publicExposure=False,
        panel='127.0.0.1:18080, unchanged',authentication='existing source-IP guard and scoped Bearer',command=command)
    if not args.apply:
        print(json.dumps(plan,ensure_ascii=False,indent=2));return
    if os.geteuid()!=0:raise SystemExit('Run on the VPS host through the authorized administrative channel')
    network=json.loads(run(['docker','inspect',CONTAINER]))[0]['NetworkSettings']['Networks']['hermes-agent-gj42_default']
    config=json.loads(Path('/etc/kipper-triagem/bridge.json').read_text())
    if network['IPAddress']!=SOURCE or network['Gateway']!=DESTINATION or config['container_ip']!=SOURCE or config['gateway_ip']!=DESTINATION:
        raise SystemExit('Existing network differs from the approved exact source/destination')
    status=run(['ufw','status'])
    if not status.startswith('Status: active'):raise SystemExit('UFW is not active; inspect before changing anything')
    if any(PORT in line and SOURCE in line for line in status.splitlines()):raise SystemExit('A matching rule exists; verify rather than repeat')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('/var/backups/kipper-triagem')/('ufw-pre-ingress-'+stamp)
    backup.mkdir(mode=0o700)
    for name in ('user.rules','user6.rules'):
        source=Path('/etc/ufw')/name
        if source.exists():
            shutil.copyfile(source,backup/name);(backup/name).chmod(0o600)
    run(command)
    lines=[line for line in run(['ufw','status']).splitlines() if PORT in line and SOURCE in line and DESTINATION in line]
    if len(lines)!=1:raise RuntimeError('Exact UFW rule not confirmed')
    result=dict(verifiedAt=datetime.now(timezone.utc).isoformat(),source=SOURCE,destination=DESTINATION,
        port=int(PORT),protocol='tcp',publicExposure=False,backup=str(backup),rule=lines[0])
    target=Path('/var/lib/kipper-triagem')/('private-ingress-'+stamp+'.json')
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
