#!/usr/bin/env python3
"""Verify public TLS/auth boundaries without printing credentials or ticket data.

Run on the VPS host after publication. Reads only the new dedicated panel login.
The invalid manual event tests JSON/Origin routing without persisting any record.
"""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
import ssl

HOST = 'kipper.jayv.cloud'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    access = json.loads(Path('/etc/kipper-triagem/panel-access.json').read_text())
    if access['url'] != 'https://' + HOST:
        raise SystemExit('Unexpected configured destination')
    credentials = base64.b64encode((access['username'] + ':' + access['password']).encode()).decode()
    opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def request(path, auth=False, origin=None, data=None, bad_password=False, http=False):
        headers = {'Content-Type': 'application/json'}
        if auth: headers['Authorization'] = 'Basic ' + credentials
        if bad_password: headers['Authorization'] = 'Basic ' + base64.b64encode((access['username'] + ':invalid-test-password').encode()).decode()
        if origin is not None: headers['Origin'] = origin
        url = ('http://' if http else 'https://') + HOST + path
        try:
            with opener.open(Request(url, data=data, headers=headers), timeout=20) as response:
                return response.status, response.headers, response.read(1_000_001)
        except HTTPError as error:
            return error.code, error.headers, error.read(1000)

    checks = {}
    for path in ('/', '/app.js', '/api/config', '/api/tickets'):
        checks['anonymous:' + path] = request(path)[0] == 401
    checks['wrongPasswordRejected'] = request('/api/config', bad_password=True)[0] == 401
    code, headers, body = request('/', auth=True)
    checks['authenticatedPanel'] = code == 200 and b'Kipper' in body
    checks['hsts'] = 'max-age=' in headers.get('Strict-Transport-Security', '')
    checks['authenticatedAssets'] = request('/app.js', auth=True)[0] == 200
    code, _, body = request('/api/config', auth=True)
    config = json.loads(body)
    checks['realAiAndKanbanModes'] = code == 200 and config == {'aiMode':'http', 'deliveryMode':'panel'}
    code, _, body = request('/api/tickets', auth=True)
    tickets = json.loads(body)
    checks['authenticatedTicketRead'] = code == 200 and isinstance(tickets, list)
    checks['foreignOriginRejected'] = request('/api/manual-events',auth=True,origin='https://example.org',data=b'{}')[0] == 403
    checks['sameOriginReachesValidation'] = request('/api/manual-events',auth=True,origin='https://' + HOST,data=b'{}')[0] == 400
    checks['transportIngressStaysPrivate'] = request('/api/events',auth=True,origin='https://' + HOST,data=b'{}')[0] == 403
    code, headers, _ = request('/', http=True)
    checks['httpRedirectsToHttps'] = code in (301,302,307,308) and headers.get('Location','').startswith('https://' + HOST)
    if not all(checks.values()):
        raise SystemExit(json.dumps(dict(passed=False,checks=checks),indent=2))
    result = dict(verifiedAt=datetime.now(timezone.utc).isoformat(),url='https://' + HOST,
        tlsCertificateAndHostnameVerified=True,authentication='HTTP Basic / dedicated evaluation account',
        checks=checks,totalTickets=len(tickets),whatsappTickets=sum(t['source']=='whatsapp-kipper' for t in tickets),
        credentialsPrinted=False,passed=True)
    target = Path('/var/lib/kipper-triagem/public-panel-verification.json')
    target.write_text(json.dumps(result,indent=2)+'\n');target.chmod(0o600)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
