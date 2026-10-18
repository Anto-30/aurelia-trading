from __future__ import annotations
import json
from runtime.notifications.meta_whatsapp import MetaWhatsAppAlertSink
def main():
    result=MetaWhatsAppAlertSink.from_env().send_now("RUNTIME_STARTUP",{"runtime_version":"meta-whatsapp-smoke-test","LIVE_EXECUTION":"BLOCKED","capital_plane_mode":"VERIFY_ONLY"})
    # Do not print provider credentials or recipient details.
    print(json.dumps({"component":"AURELIA","meta_whatsapp_test":result},sort_keys=True))
    return 0 if result.get("status")=="SENT" else 1
if __name__=="__main__": raise SystemExit(main())
