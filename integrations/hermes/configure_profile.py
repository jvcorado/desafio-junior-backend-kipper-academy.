"""One-time, owner-run configuration of the explicitly approved two-member test group."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
from datetime import datetime, timezone
from urllib.request import urlopen
import hermes_yaml as yaml


def strings(value):
    return [x.strip() for x in value.split(',') if x.strip()] if isinstance(value,str) else list(value or [])


def atomic(path, text):
    tmp = path.with_name(path.name+'.kipper-new')
    fd = os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        output.write(text)
    os.replace(tmp,path)


def main():
    data=json.load(sys.stdin)
    chat=data['chat_id']
    if not re.fullmatch(r'[0-9]+@g\.us',chat):
        raise ValueError('Expected WhatsApp group JID')
    with urlopen('http://127.0.0.1:3000/chat/'+chat,timeout=10) as response:
        metadata=json.load(response)
    if metadata.get('name')!='Kipper · Triagem de teste' or len(metadata.get('participants',[]))!=2:
        raise ValueError('Group name/membership differs from the approved JV and JAYV test group')
    home=Path('/opt/data')
    profile=home/'profiles/kipper-triagem'
    source=Path('/tmp/kipper-profile-bundle')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=profile/'backups'/('activation-'+stamp)
    backup.mkdir(mode=0o700,parents=True)
    for path in (home/'config.yaml',profile/'config.yaml',profile/'SOUL.md'):
        if path.exists():
            destination=backup/(('default-' if path.parent==home else '')+path.name)
            shutil.copyfile(path,destination);destination.chmod(0o600)
    cfg=yaml.safe_load((home/'config.yaml').read_text()) or {}
    pcfg=yaml.safe_load((profile/'config.yaml').read_text()) or {}
    routes=cfg.setdefault('gateway',{}).setdefault('profile_routes',[])
    before=hashlib.sha256(json.dumps(routes,sort_keys=True).encode()).hexdigest()
    if any(r.get('chat_id')==chat for r in routes):
        raise ValueError('Group already has a route: inspect before modifying')
    routes.append(dict(name='kipper-triagem-test',platform='whatsapp',profile='kipper-triagem',chat_id=chat,bot_profile='default',enabled=True))
    # Add only this group; retain existing policy and every existing list entry.
    from dotenv import dotenv_values
    env=dotenv_values(home/'.env')
    whatsapp=cfg.setdefault('whatsapp',{})
    nested=((cfg.get('platforms') or {}).get('whatsapp') or {}).get('extra') or {}
    for key,envkey in [('group_allow_from','WHATSAPP_GROUP_ALLOWED_USERS'),('free_response_chats','WHATSAPP_FREE_RESPONSE_CHATS')]:
        existing=strings(whatsapp.get(key,nested.get(key,env.get(envkey,''))))
        if chat not in existing:existing.append(chat)
        whatsapp[key]=existing
    plugins=pcfg.setdefault('plugins',{})
    enabled=plugins.setdefault('enabled',[])
    if 'kipper-support' not in enabled:enabled.append('kipper-support')
    plugins['disabled']=[p for p in plugins.get('disabled',[]) if p!='kipper-support']
    allowed=['kipper_support','skills',*['mcp-'+name for name in (pcfg.get('mcp_servers') or {})]]
    for platform in ('whatsapp','api_server'):
        pcfg.setdefault('platform_toolsets',{})[platform]=allowed
    target=profile/'plugins/kipper-support'
    if target.exists():raise ValueError('Plugin already exists; inspect before replacing')
    shutil.copytree(source/'kipper_plugin',target)
    old_soul=(profile/'SOUL.md').read_text() if (profile/'SOUL.md').exists() else ''
    marker='<!-- segundo-cerebro-jv -->'
    soul=(source/'SOUL.md').read_text()
    if marker in old_soul and marker not in soul:soul+='\n'+marker+old_soul.split(marker,1)[1]
    atomic(profile/'SOUL.md',soul)
    atomic(profile/'kipper-ingress.json',json.dumps(dict(chat_id=chat,url=data['url'],key=data['key'])))
    atomic(profile/'config.yaml',yaml.safe_dump(pcfg,sort_keys=False,allow_unicode=True))
    atomic(home/'config.yaml',yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True))
    # Fixed scope only: reload this profile's tools, then ask for a graceful, draining restart
    # so the primary transport sees the new exact-chat route and allow-list entry.
    from gateway.control_socket import query_gateway_control,reload_gateway_plugins
    plugin_result=reload_gateway_plugins(home,profile_home=profile,timeout=30) or {}
    identity=query_gateway_control(home,'identify',timeout=5) or {}
    pid=identity.get('pid')
    result=dict(configuredAt=datetime.now(timezone.utc).isoformat(),profile='kipper-triagem',
        groupName=metadata['name'],participants=2,routeCountBefore=len(routes)-1,routeCountAfter=len(routes),
        previousRoutesDigest=before,existingRoutesPreserved=True,pluginReloaded=plugin_result.get('reloaded',False),
        toolsets=allowed,backup=str(backup),gatewayRestartRequested=False)
    if isinstance(pid,int) and pid>1:
        os.kill(pid,signal.SIGUSR1)
        result['gatewayRestartRequested']=True
    atomic(profile/'kipper-activation-receipt.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
