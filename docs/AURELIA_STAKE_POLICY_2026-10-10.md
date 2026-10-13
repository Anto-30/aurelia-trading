# AURELIA Stake and Probability Policy — revised 2026-10-13

This revision supersedes the 2026-10-10 probability threshold and fixed-minimum assumptions.

## Probability threshold

A live candidate's estimated trade probability must be within the inclusive range **55% to 75%**. Values outside the range are rejected, never clipped. The numeric band is only one gate: probability must also be calibrated, fresh, and free of unresolved drift, and the trade must have positive expected value after execution costs, slippage, and quote costs. A probability within the band is not proof of a profitable edge.

## Balance-scaled stake

The previous USD 1.00 minimum was a starting assumption, not a universal broker constraint. For each live authorization, AURELIA must have a fresh, source-bound broker-reported minimum stake for the exact contract. This policy requires the independently verified real account currency to be USD; a non-USD account is blocked rather than treating one unit of another currency as one dollar. For purchased contracts, stake is treated as the contractual maximum loss.

For each live authorization, the canonical sizing rule is:

`authorized_stake = floor_to_cent(verified_available_balance × 0.01)`

This makes the stake rise and fall with fresh, verified USD available balance while capping the purchased-contract loss budget at 1% of available capital. The user/strategy-proposed stake is not allowed to bypass the deterministic sizing result. Existing Risk Warden, exposure, economics, calibration, freshness, account-isolation, reconciliation, watchdog, kill-switch, and release gates remain mandatory.

The 1% risk budget must be at least the exact contract's broker-reported minimum. For example, a verified balance of USD 145.00 yields a USD 1.45 risk budget; if the broker minimum is USD 1.50, the order is unaffordable and must be blocked. A verified balance of USD 1.45 yields only USD 0.01 after rounding down, so it cannot fund a USD 1.00 or USD 1.50 minimum. AURELIA must not silently increase the risk percentage or force a minimum stake above the budget.

| Verified available balance | Computed 1% risk budget | Outcome if broker minimum is USD 1.00 | Outcome if broker minimum is USD 1.50 |
|---:|---:|---|---|
| 1.45 | 0.01 | Blocked | Blocked |
| 50.00 | 0.50 | Blocked | Blocked |
| 99.99 | 0.99 | Blocked | Blocked |
| 100.00 | 1.00 | 1.00 | Blocked |
| 145.00 | 1.45 | 1.45 | Blocked |
| 150.00 | 1.50 | 1.50 | 1.50 |
| 200.00 | 2.00 | 2.00 | 2.00 |
| 350.99 | 3.50 | 3.50 | 3.50 |

The sizing calculation uses available balance rather than stale UI state or an assumed deposit. It rounds down to cents. If available balance falls, the next authorized stake decreases; if the balance, contract minimum, or minimum's freshness/source binding is invalid or stale, no live authorization is permitted. The current Deriv adapter does not yet provide a source-bound minimum-stake value, so LIVE authorization remains blocked until that integration is implemented and verified.

## Go-live status is separate

Changing these parameters does **not** enable live trading. The checked-in live lock remains authoritative. An authenticated Deriv session, exact real-account binding and currency, current balance evidence, a real broker transaction/fill lifecycle with reconciliation, a production runtime/soak, and strategy-specific OOS, calibration/drift, and net-economics qualification must still be independently evidenced before a release can be authorized.
