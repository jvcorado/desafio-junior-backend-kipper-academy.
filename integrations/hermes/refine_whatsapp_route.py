"""Narrow the existing test route to its verified sender; preserve every other route."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import hermes_yaml as yaml


def digest(routes):
    return hashlib.sha256(json.dumps(routes,sort_keys=True).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sender-session',required=True)
    args=parser.parse_args()
    home=Path('/opt/data');path=home/'config.yaml'
    config=yaml.safe_load(path.read_text())
    routes=config['gateway']['profile_routes']
    matches=[r for r in routes if r.get('name')=='kipper-triagem-test' and r.get('profile')=='kipper-triagem']
    if len(matches)!=1:raise ValueError('Expected exactly one existing Kipper route')
    route=matches[0]
    if route.get('user_id'):raise ValueError('Route already restricted; inspect before repeating')
    with sqlite3.connect('file:/opt/data/state.db?mode=ro',uri=True) as db:
        sender=db.execute('SELECT user_id FROM sessions WHERE id=? AND chat_id=? AND source=?',
            (args.sender_session,route['chat_id'],'whatsapp')).fetchone()
    if not sender or not sender[0]:raise ValueError('Session must be from the approved test group')
    before=digest([r for r in routes if r is not route])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=home/'profiles/kipper-triagem/backups'/('default-config-pre-sender-'+stamp+'.yaml')
    fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write(path.read_text())
    route['user_id']=sender[0]
    from gateway.profile_routing import parse_profile_routes,match_profile_route
    selected=match_profile_route(parse_profile_routes(routes),platform='whatsapp',chat_id=route['chat_id'],user_id=sender[0],adapter_profile='default')
    if selected is None or selected.profile!='kipper-triagem':raise ValueError('A more specific route still overrides Kipper')
    if digest([r for r in routes if r is not route])!=before:raise ValueError('Unrelated route changed')
    tmp=path.with_name(path.name+'.kipper-sender-new')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write(yaml.safe_dump(config,sort_keys=False,allow_unicode=True))
    os.replace(tmp,path)
    from gateway.control_socket import query_gateway_control
    identity=query_gateway_control(home,'identify') or {}
    pid=identity.get('pid')
    result=dict(verifiedAt=datetime.now(timezone.utc).isoformat(),profile='kipper-triagem',
        senderRestricted=True,routeRank=selected.specificity,unrelatedRoutesPreserved=True,
        unrelatedRoutesDigest=before,backup=str(backup),gatewayRestartRequested=False)
    if isinstance(pid,int) and pid>1:
        os.kill(pid,signal.SIGUSR1);result['gatewayRestartRequested']=True
    receipt=home/'profiles/kipper-triagem/kipper-route-precedence-receipt.json'
    fd=os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
