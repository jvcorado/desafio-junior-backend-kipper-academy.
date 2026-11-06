import importlib.util
import json
from pathlib import Path
from http.server import ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec=importlib.util.spec_from_file_location('private_bridge',Path(__file__).parent/'private_bridge.py')
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class PrivateBridgeBoundaryTest(unittest.TestCase):
    def setUp(self):
        bridge.SECRETS=dict(ai_key='test-ai',ingress_key='test-ingress',container_ip='127.0.0.1')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),bridge.Handler)
        self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def request(self,path,key='test-ingress',data=None):
        request=Request('http://127.0.0.1:'+str(self.port)+path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=2) as response:return response.status,json.load(response)
        except HTTPError as response:return response.code,json.load(response)

    def ingress(self):
        # Only the classification of this test listener changes; its socket remains loopback.
        self.server.server_address=('172.16.6.1',self.port)

    def test_no_bearer_means_no_inference(self):
        with patch.object(bridge.subprocess,'run') as worker:
            self.assertEqual(403,self.request('/v1/chat/completions',key='wrong',data={})[0])
            worker.assert_not_called()

    def test_ingress_does_not_expose_master_actions(self):
        self.ingress()
        with patch.object(bridge,'backend') as backend:
            for path in ['/api/policies','/api/manual-events','/api/conflicts','/api/tickets/x/retry']:
                self.assertEqual(404,self.request(path,data={})[0])
            backend.assert_not_called()

    def test_ingress_rejects_non_whatsapp_source(self):
        self.ingress()
        with patch.object(bridge,'backend') as backend:
            self.assertEqual(400,self.request('/api/events',data={'source':'panel-test'})[0])
            backend.assert_not_called()

    def test_ingress_cannot_process_another_source_ticket(self):
        self.ingress()
        with patch.object(bridge,'backend',return_value=(200,b'{"ticket":{"source":"panel-test"}}')) as backend:
            self.assertEqual(404,self.request('/api/tickets/11111111-1111-1111-1111-111111111111/process',data={})[0])
            self.assertEqual(1,backend.call_count)
            self.assertEqual('GET',backend.call_args.args[0])

    def test_inference_rejects_other_tools(self):
        with patch.object(bridge.subprocess,'run') as worker:
            self.assertEqual(400,self.request('/v1/chat/completions',key='test-ai',data={'tools':[{'function':{'name':'terminal'}}]})[0])
            worker.assert_not_called()


if __name__=='__main__':unittest.main()
