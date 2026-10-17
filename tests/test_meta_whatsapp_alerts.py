from __future__ import annotations
import json, os, unittest
from unittest.mock import patch
import runtime.notifications.meta_whatsapp as meta
from runtime.notifications.meta_whatsapp import MetaWhatsAppAlertSink, MetaWhatsAppConfig

def cfg(**kw):
    d=dict(enabled=True,token="TEST_TOKEN",phone_id="123456789012345",recipient="+254700000000",template="aurelia_alert",language="en_US",version="v25.0",timeout=8.0,dedupe_seconds=300.0,errors=())
    d.update(kw); return MetaWhatsAppConfig(**d)

class Tests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ,{"AURELIA_WHATSAPP_ALERTS":"false"},clear=False): sink=MetaWhatsAppAlertSink.from_env()
        self.assertEqual(sink.send_now("RUNTIME_STARTUP")["status"],"DISABLED")
    def test_missing_config_fails_closed(self):
        with patch.dict(os.environ,{"AURELIA_WHATSAPP_ALERTS":"true"},clear=True): sink=MetaWhatsAppAlertSink.from_env()
        self.assertFalse(sink.status()["ready"])
        self.assertIn("META_WHATSAPP_ACCESS_TOKEN_MISSING",sink.status()["configuration_errors"])
    def test_valid_configuration_shape_is_accepted(self):
        env={"AURELIA_WHATSAPP_ALERTS":"true","META_WHATSAPP_ACCESS_TOKEN":"TEST_TOKEN","META_WHATSAPP_PHONE_NUMBER_ID":"123456789012345","META_WHATSAPP_TO":"+254700000000","META_WHATSAPP_TEMPLATE_NAME":"aurelia_alert","META_WHATSAPP_TEMPLATE_LANGUAGE":"en_US","META_WHATSAPP_API_VERSION":"v25.0"}
        with patch.dict(os.environ,env,clear=True): sink=MetaWhatsAppAlertSink.from_env()
        self.assertTrue(sink.status()["ready"],sink.status()["configuration_errors"])
    def test_template_payload_and_meta_acceptance(self):
        got={}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return json.dumps({"messages":[{"id":"wamid.TEST"}]}).encode()
        def fake(req,timeout):
            got["url"]=req.full_url; got["body"]=json.loads(req.data); got["auth"]=req.get_header("Authorization"); return Response()
        with patch.object(meta,"urlopen",fake):
            result=MetaWhatsAppAlertSink(cfg()).send_now("RUNTIME_STARTUP",{"runtime_version":"test","LIVE_EXECUTION":"BLOCKED","access_token":"should-not-appear"})
        self.assertEqual(result["message_id"],"wamid.TEST")
        self.assertIn("/v25.0/123456789012345/messages",got["url"])
        self.assertEqual(got["body"]["template"]["name"],"aurelia_alert")
        self.assertNotIn("should-not-appear",json.dumps(got["body"]))
        self.assertTrue(got["auth"].startswith("Bearer "))
    def test_healthy_reconciliation_filtered(self):
        self.assertEqual(MetaWhatsAppAlertSink(cfg()).send_now("RECONCILIATION",{"healthy":True})["status"],"FILTERED")
    def test_no_message_id_is_failure(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return b'{"messages":[]}'
        with patch.object(meta,"urlopen",lambda req,timeout:Response()):
            with self.assertRaisesRegex(RuntimeError,"ACCEPTANCE_ID_MISSING"): MetaWhatsAppAlertSink(cfg()).send_now("RUNTIME_STARTUP",{})
if __name__=="__main__": unittest.main()
