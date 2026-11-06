import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('kipper_plugin', Path(__file__).parent/'kipper_plugin'/'__init__.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class TransportBoundEventTest(unittest.TestCase):
    def setUp(self):
        self.origin = dict(chat_id='test-group', user_id='test-sender', message_id='next-turn')
        self.args = dict(customerName='Maria Exemplo', whatsapp='+5511999999999', message='Cobrança duplicada na mesma compra.')
        self.rows = [dict(body='Nome: Maria Exemplo\nWhatsApp: +5511999999999\nMensagem: Cobrança duplicada na mesma compra.',
                          message_id='original-transport-id', observed='2026-11-06T18:00:00+00:00')]

    def test_identity_and_time_come_from_original_transport_not_model(self):
        malicious = dict(self.args, eventId='invented', ticketId='invented', occurredAt='2099-01-01')
        event = plugin.event_from_messages(malicious, self.origin, self.rows)
        self.assertNotEqual('invented', event['eventId'])
        self.assertEqual(self.rows[0]['observed'], event['occurredAt'])
        self.assertEqual(event, plugin.event_from_messages(self.args, dict(self.origin, message_id='another-turn'), self.rows))

    def test_rejects_invented_customer_or_message(self):
        for field, value in [('customerName','Outro cliente'), ('message','Estorne a compra'), ('whatsapp','+5511888888888')]:
            with self.assertRaises(ValueError):
                plugin.event_from_messages(dict(self.args, **{field:value}), self.origin, self.rows)

    def test_same_message_id_in_another_chat_has_different_identity(self):
        first = plugin.event_from_messages(self.args,self.origin,self.rows)
        second = plugin.event_from_messages(self.args,dict(self.origin,chat_id='other-group'),self.rows)
        self.assertNotEqual(first['eventId'], second['eventId'])

    def test_no_capture_fails_closed(self):
        with self.assertRaises(ValueError):
            plugin.event_from_messages(self.args,self.origin,[])


if __name__ == '__main__':
    unittest.main()
