# AURELIA Deriv authenticated-session verification

This workflow verifies the external broker prerequisite without submitting an order.

It uses AURELIA's existing session chain:

Bearer credential -> exact account binding -> fresh OTP -> authenticated Options WebSocket -> identity/currency/environment verification -> fresh balance snapshot.

For a real-money verification, `DERIV_EXPECTED_LOGINID` is mandatory. OAuth access tokens do not require `DERIV_APP_ID`; PAT authentication does.

The verification result intentionally reports only that the balance was freshly verified, not the monetary amount. The OTP is redacted and never written to logs. The workflow always asserts:

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

Successful execution of this workflow establishes a genuine authenticated broker-session/balance observation. It does not by itself promote a strategy, authorize live trading, or satisfy the full production evidence bundle.
