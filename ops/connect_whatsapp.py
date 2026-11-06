#!/usr/bin/env python3
"""Install the domain-only profile plugin and bind the explicitly approved JV/JAYV group."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

CONTAINER='hermes-agent-gj42-hermes-agent-1'


def run(args,**kwargs):
    result=subprocess.run(args,capture_output=True,**kwargs)
    if result.returncode:raise RuntimeError('Profile configuration failed; inspect private host state without exposing credentials')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--chat',required=True)
    parser.add_argument('--sender-session',help='Existing fictitious WhatsApp session in this group; pins its verified sender and outranks user-only routes')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if hashlib.sha256(args.bundle.read_bytes()).hexdigest()!=args.sha256:raise SystemExit('Checksum mismatch')
    if not args.apply:
        print(json.dumps(dict(profile='kipper-triagem',group='Kipper · Triagem de teste',members='JV and JAYV only',
            tools='register/check support + existing memory',route='exact chat, preserves existing routes',
            restart='graceful drain through existing supervisor'),indent=2));return
    if os.geteuid()!=0:raise SystemExit('Execute on the VPS host through the existing authorized admin channel')
    with tempfile.TemporaryDirectory(prefix='kipper-profile-') as work:
        with tarfile.open(args.bundle) as archive:
            archive.extractall(work,filter='data')
        root=Path(work)
        expected={'SOUL.md','configure_profile.py','kipper_plugin/__init__.py','kipper_plugin/plugin.yaml'}
        if {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}!=expected:raise SystemExit('Unexpected bundle contents')
        run(['docker','cp',str(root)+'/.',CONTAINER+':/tmp/kipper-profile-bundle'])
        run(['docker','exec','--user','0',CONTAINER,'chmod','-R','a+rX,go-w','/tmp/kipper-profile-bundle'])
        secret=json.loads(Path('/etc/kipper-triagem/bridge.json').read_text())
        payload=dict(chat_id=args.chat,url='http://'+secret['gateway_ip']+':18081',key=secret['ingress_key'])
        if args.sender_session:payload['sender_session']=args.sender_session
        result=run(['docker','exec','-i','--user','10000:10000','-e',
            'PYTHONPATH=/opt/hermes:/opt/hermes/.venv/lib/python3.14/site-packages',CONTAINER,
            '/opt/hermes/.venv/bin/python','/tmp/kipper-profile-bundle/configure_profile.py'],input=json.dumps(payload).encode(),timeout=90)
        print(result.stdout.decode())


if __name__=='__main__':main()
