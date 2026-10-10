# AURELIA Stake and Probability Policy — 2026-10-10

## Probability threshold

A live candidate's estimated trade probability must be within the inclusive range **50% to 75%**. Values outside the range are rejected, never clipped. The numeric band is only one gate: probability must also be calibrated, fresh, and free of unresolved drift, and the trade must have positive expected value after execution costs, slippage, and quote costs. A 50% probability is not inherently profitable.

## Balance-scaled stake

The starting stake reference and execution minimum are **USD 1.00**. This policy requires the independently verified real account currency to be USD; a non-USD account is blocked rather than treating one unit of another currency as one dollar. For purchased contracts, stake is treated as the contractual maximum loss.

For each live authorization, the canonical sizing rule is:

`authorized_stake = floor_to_cent(verified_available_balance × 0.01)`

This makes the stake rise and fall with fresh, verified USD available balance while capping the purchased-contract loss budget at 1% of available capital. The user/strategy-proposed stake is not allowed to bypass the deterministic sizing result. Existing Risk Warden, exposure, economics, calibration, freshness, account-isolation, reconciliation, watchdog, kill-switch, and release gates remain mandatory.

Because the minimum stake is 1.00, the 1% risk budget cannot fund an order until verified available USD available balance is at least USD 100.00. This is a hard mathematical constraint, not an operational setting to work around. For example, a 1.45 balance cannot safely support a 1.00 maximum-loss stake under a 1% per-trade risk limit. In that case AURELIA must block live trading; it must not silently increase the risk percentage or force a minimum stake above the budget.

| Verified available balance | Computed 1% risk budget | Live stake outcome |
|---:|---:|---|
| 50.00 | 0.50 | Blocked: below minimum |
| 99.99 | 0.99 | Blocked: below minimum |
| 100.00 | 1.00 | 1.00 |
| 150.00 | 1.50 | 1.50 |
| 200.00 | 2.00 | 2.00 |
| 350.99 | 3.50 | 3.50 |

The sizing calculation uses available balance rather than stale UI state or an assumed deposit. It rounds down to cents. If available balance falls, the next authorized stake decreases; if the balance becomes invalid or stale, no live authorization is permitted.

## Go-live status is separate

Changing these parameters does **not** enable live trading. The checked-in live lock remains authoritative. An authenticated Deriv session, exact real-account binding and currency, current balance evidence, a real broker transaction/fill lifecycle with reconciliation, a production runtime/soak, and strategy-specific OOS, calibration/drift, and net-economics qualification must still be independently evidenced before a release can be authorized.
